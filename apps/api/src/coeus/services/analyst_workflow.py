from dataclasses import replace
from uuid import UUID

from coeus.core.errors import AppError
from coeus.core.permissions import Permission
from coeus.domain.auth import RoleName, UserAccount
from coeus.domain.enums import TicketState
from coeus.domain.state_machine import can_transition
from coeus.domain.tickets import (
    AnalystNote,
    RoutingRoute,
    TicketRecord,
    WorkPackageStatus,
)
from coeus.repositories.access import SeedAccessRepository
from coeus.services.analyst_drafts import DraftProductInput, draft_asset, new_uuid, now
from coeus.services.analyst_records import (
    all_work_packages_complete,
    approved_route,
    assigned_to,
    assignment_record,
    default_work_package_titles,
    draft_version,
    latest_assignment,
    linked_product_record,
    next_draft_version,
    work_package_records,
)
from coeus.services.audit import AuditLog
from coeus.services.store import StoreServices
from coeus.services.ticket_records import timeline
from coeus.services.tickets import TicketServices

ACTIVE_ANALYST_STATES = {TicketState.ANALYST_IN_PROGRESS, TicketState.REWORK_REQUIRED}
ANALYST_READ_PERMISSIONS = frozenset({Permission.ANALYST_WORK})
ASSIGNMENT_READ_PERMISSIONS = frozenset({Permission.RFA_ASSIGN, Permission.COLLECTION_ASSIGN})


class AnalystWorkflowService:
    def __init__(
        self,
        tickets: TicketServices,
        store: StoreServices,
        access_repository: SeedAccessRepository,
        audit_log: AuditLog,
    ) -> None:
        self._tickets = tickets
        self._store = store
        self._access = access_repository
        self._audit_log = audit_log

    def analyst_candidates(self, actor: UserAccount) -> tuple[UserAccount, ...]:
        self._require_any(actor, {Permission.RFA_ASSIGN, Permission.COLLECTION_ASSIGN})
        return tuple(
            user
            for user in self._access.list_users()
            if user.is_active and RoleName.INTELLIGENCE_ANALYST in user.roles
        )

    def assign(
        self,
        actor: UserAccount,
        ticket_id: UUID,
        analyst_user_id: UUID,
        work_package_titles: tuple[str, ...],
        team_name: str | None = None,
    ) -> TicketRecord:
        self._require_any(actor, {Permission.RFA_ASSIGN, Permission.COLLECTION_ASSIGN})
        ticket = self._tickets.tickets.get_workflow_ticket(
            actor, ticket_id, ASSIGNMENT_READ_PERMISSIONS
        )
        if ticket.state != TicketState.ANALYST_ASSIGNMENT:
            raise AppError(409, "invalid_ticket_state", "Ticket is not awaiting assignment.")
        if latest_assignment(ticket) is not None:
            raise AppError(409, "analyst_already_assigned", "Ticket already has an analyst.")
        route = approved_route(ticket)
        if route is None:
            raise AppError(409, "route_not_approved", "Ticket has no approved route.")
        self._require_assignment_permission(actor, route)
        analyst = self._access.get_user(analyst_user_id)
        if (
            analyst is None
            or not analyst.is_active
            or RoleName.INTELLIGENCE_ANALYST not in analyst.roles
        ):
            raise AppError(422, "invalid_analyst", "Assigned user must be an active analyst.")
        titles = _normalise_titles(work_package_titles) or default_work_package_titles(
            ticket, route
        )
        assignment_team = _normalise_team_name(team_name) or _suggested_team_name(ticket, route)
        target_state = TicketState.ANALYST_IN_PROGRESS
        self._ensure_transition(ticket.state, target_state)
        assignment = assignment_record(
            ticket.ticket_id, analyst.user_id, actor.user_id, route, assignment_team
        )
        packages = work_package_records(ticket.ticket_id, titles)
        updated = self._tickets.tickets.save_system_update(
            replace(
                ticket,
                state=target_state,
                analyst_assignments=(*ticket.analyst_assignments, assignment),
                work_packages=(*ticket.work_packages, *packages),
                timeline=(
                    *ticket.timeline,
                    timeline(
                        ticket.ticket_id,
                        actor.user_id,
                        "analyst_assigned",
                        _assignment_summary(analyst.username, assignment_team),
                    ),
                ),
            )
        )
        metadata = {
            "ticket_id": str(ticket.ticket_id),
            "analyst_user_id": str(analyst.user_id),
        }
        if assignment_team:
            metadata["team_name"] = assignment_team
        self._audit_log.record("analyst_assigned", str(actor.user_id), metadata)
        return updated

    def list_tasks(self, actor: UserAccount) -> tuple[TicketRecord, ...]:
        self._require(actor, Permission.ANALYST_WORK)
        return tuple(
            ticket
            for ticket in self._tickets.tickets.list_workflow_tickets(
                actor, ANALYST_READ_PERMISSIONS
            )
            if assigned_to(ticket, actor.user_id)
            and ticket.state in {*ACTIVE_ANALYST_STATES, TicketState.QC_REVIEW}
        )

    def task_details(self, actor: UserAccount, ticket_id: UUID) -> TicketRecord:
        self._require(actor, Permission.ANALYST_WORK)
        ticket = self._tickets.tickets.get_workflow_ticket(
            actor, ticket_id, ANALYST_READ_PERMISSIONS
        )
        if not assigned_to(ticket, actor.user_id):
            raise AppError(404, "task_not_found", "Analyst task was not found.")
        return ticket

    def add_note(self, actor: UserAccount, ticket_id: UUID, body: str) -> TicketRecord:
        ticket = self._active_task(actor, ticket_id)
        note = AnalystNote(
            note_id=new_uuid(),
            ticket_id=ticket.ticket_id,
            body=body,
            created_by_user_id=actor.user_id,
            created_at=now(),
        )
        updated = self._tickets.tickets.save_system_update(
            replace(
                ticket,
                analyst_notes=(*ticket.analyst_notes, note),
                timeline=(
                    *ticket.timeline,
                    timeline(ticket.ticket_id, actor.user_id, "analyst_note_added", body),
                ),
            )
        )
        self._audit_log.record(
            "analyst_note_added",
            str(actor.user_id),
            {"ticket_id": str(ticket_id)},
        )
        return updated

    def link_product(self, actor: UserAccount, ticket_id: UUID, product_id: UUID) -> TicketRecord:
        ticket = self._active_task(actor, ticket_id)
        if any(link.product_id == product_id for link in ticket.linked_products):
            raise AppError(409, "product_already_linked", "Product is already linked.")
        product = self._store.details.get_visible_product(actor, product_id)
        link = linked_product_record(
            ticket.ticket_id,
            product.product_id,
            product.reference,
            product.metadata.title,
            product.metadata.summary,
            actor.user_id,
        )
        updated = self._tickets.tickets.save_system_update(
            replace(
                ticket,
                linked_products=(*ticket.linked_products, link),
                timeline=(
                    *ticket.timeline,
                    timeline(ticket.ticket_id, actor.user_id, "analyst_product_linked", link.title),
                ),
            )
        )
        self._audit_log.record(
            "analyst_product_linked",
            str(actor.user_id),
            {"ticket_id": str(ticket_id), "product_id": str(product_id)},
        )
        return updated

    def update_work_package(
        self, actor: UserAccount, ticket_id: UUID, package_id: UUID, status: WorkPackageStatus
    ) -> TicketRecord:
        ticket = self._active_task(actor, ticket_id)
        packages = tuple(
            replace(package, status=status) if package.package_id == package_id else package
            for package in ticket.work_packages
        )
        if packages == ticket.work_packages:
            raise AppError(404, "work_package_not_found", "Work package was not found.")
        return self._tickets.tickets.save_system_update(
            replace(
                ticket,
                work_packages=packages,
                timeline=(
                    *ticket.timeline,
                    timeline(ticket.ticket_id, actor.user_id, "work_package_updated", status.value),
                ),
            )
        )

    def create_draft(
        self, actor: UserAccount, ticket_id: UUID, draft: DraftProductInput
    ) -> TicketRecord:
        ticket = self._active_task(actor, ticket_id)
        assets = tuple(draft_asset(asset) for asset in draft.assets)
        version = draft_version(
            ticket.ticket_id,
            next_draft_version(ticket),
            draft.title,
            draft.summary,
            draft.product_type,
            draft.content,
            assets,
            actor.user_id,
        )
        updated = self._tickets.tickets.save_system_update(
            replace(
                ticket,
                draft_products=(*ticket.draft_products, version),
                timeline=(
                    *ticket.timeline,
                    timeline(ticket.ticket_id, actor.user_id, "draft_product_saved", draft.title),
                ),
            )
        )
        self._audit_log.record(
            "draft_product_saved",
            str(actor.user_id),
            {"ticket_id": str(ticket_id)},
        )
        return updated

    def submit_to_qc(self, actor: UserAccount, ticket_id: UUID) -> TicketRecord:
        self._require(actor, Permission.ANALYST_SUBMIT_PRODUCT)
        ticket = self._active_task(actor, ticket_id)
        if not ticket.draft_products:
            raise AppError(409, "draft_required", "A draft product is required before QC.")
        if not all_work_packages_complete(ticket):
            raise AppError(409, "work_packages_incomplete", "Complete work packages before QC.")
        self._ensure_transition(ticket.state, TicketState.QC_REVIEW)
        updated = self._tickets.tickets.save_system_update(
            replace(
                ticket,
                state=TicketState.QC_REVIEW,
                timeline=(
                    *ticket.timeline,
                    timeline(
                        ticket.ticket_id,
                        actor.user_id,
                        "submitted_to_qc",
                        "Submitted to QC.",
                    ),
                ),
            )
        )
        self._audit_log.record("submitted_to_qc", str(actor.user_id), {"ticket_id": str(ticket_id)})
        return updated

    def _active_task(self, actor: UserAccount, ticket_id: UUID) -> TicketRecord:
        ticket = self.task_details(actor, ticket_id)
        if ticket.state not in ACTIVE_ANALYST_STATES:
            raise AppError(409, "invalid_ticket_state", "Analyst task is not in progress.")
        return ticket

    @staticmethod
    def _require(actor: UserAccount, permission: Permission) -> None:
        if permission not in actor.permissions:
            raise AppError(403, "forbidden", "Permission denied.")

    @staticmethod
    def _require_any(actor: UserAccount, permissions: set[Permission]) -> None:
        if not permissions.intersection(actor.permissions):
            raise AppError(403, "forbidden", "Permission denied.")

    def _require_assignment_permission(self, actor: UserAccount, route: RoutingRoute) -> None:
        permission = (
            Permission.RFA_ASSIGN if route == RoutingRoute.RFA else Permission.COLLECTION_ASSIGN
        )
        self._require(actor, permission)

    @staticmethod
    def _ensure_transition(current: TicketState, target: TicketState) -> None:
        if not can_transition(current, target):
            raise AppError(409, "invalid_ticket_state", "Ticket cannot move to that state.")


def build_analyst_workflow_service(
    tickets: TicketServices,
    store: StoreServices,
    access_repository: SeedAccessRepository,
    audit_log: AuditLog,
) -> AnalystWorkflowService:
    return AnalystWorkflowService(tickets, store, access_repository, audit_log)


def _normalise_titles(titles: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(title.strip() for title in titles if title.strip()))


def _normalise_team_name(team_name: str | None) -> str | None:
    if team_name is None:
        return None
    cleaned = " ".join(team_name.split())
    return cleaned[:120] or None


def _suggested_team_name(ticket: TicketRecord, route: RoutingRoute) -> str | None:
    if route == RoutingRoute.RFA and ticket.rfa_reviews:
        return ticket.rfa_reviews[-1].suggested_team_name
    if route == RoutingRoute.CM and ticket.cm_reviews:
        return ticket.cm_reviews[-1].suggested_collection_team_name
    return None


def _assignment_summary(username: str, team_name: str | None) -> str:
    if team_name:
        return f"{username} assigned via {team_name}."
    return username
