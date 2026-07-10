from dataclasses import replace
from uuid import UUID

from coeus.core.errors import AppError
from coeus.core.permissions import Permission
from coeus.domain.auth import RoleName, UserAccount
from coeus.domain.enums import TicketState
from coeus.domain.state_machine import can_transition
from coeus.domain.tickets import (
    AnalystNote,
    LinkedAnalystProduct,
    RoutingRoute,
    TicketRecord,
    WorkPackageStatus,
)
from coeus.repositories.access import AccessRepository
from coeus.services.analyst_assignment import assignment_change
from coeus.services.analyst_drafts import DraftProductInput, draft_asset, new_uuid, now
from coeus.services.analyst_records import (
    all_work_packages_complete,
    approved_route,
    assigned_to,
    draft_version,
    latest_assignment,
    linked_product_record,
    next_draft_version,
)
from coeus.services.audit import AuditLog
from coeus.services.audit_rollback import record_ticket_audit_or_rollback
from coeus.services.store import StoreServices
from coeus.services.ticket_records import timeline
from coeus.services.tickets import TicketServices

ACTIVE_ANALYST_STATES = {TicketState.ANALYST_IN_PROGRESS, TicketState.REWORK_REQUIRED}
ANALYST_READ_PERMISSIONS = frozenset({Permission.ANALYST_WORK})
ANALYST_TASK_LIST_LIMIT = 100
ANALYST_LINKED_PRODUCT_LIMIT = 25
ASSIGNMENT_READ_PERMISSIONS = frozenset({Permission.RFA_ASSIGN, Permission.COLLECTION_ASSIGN})


class AnalystWorkflowService:
    def __init__(
        self,
        tickets: TicketServices,
        store: StoreServices,
        access_repository: AccessRepository,
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
        # Managers may reassign an in-progress ticket, e.g. after an analyst
        # account is deactivated; the state stays ANALYST_IN_PROGRESS.
        reassignment = ticket.state == TicketState.ANALYST_IN_PROGRESS
        if ticket.state not in {TicketState.ANALYST_ASSIGNMENT, TicketState.ANALYST_IN_PROGRESS}:
            raise AppError(409, "invalid_ticket_state", "Ticket is not awaiting assignment.")
        if not reassignment and latest_assignment(ticket) is not None:
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
        target_state = TicketState.ANALYST_IN_PROGRESS
        if not reassignment:
            self._ensure_transition(ticket.state, target_state)
        change = assignment_change(
            ticket,
            actor,
            analyst,
            route,
            work_package_titles,
            team_name,
            reassignment=reassignment,
        )
        updated = self._tickets.tickets.save_system_update(change.ticket)
        self._record_audit_or_rollback(ticket, change.event_type, actor, change.audit_metadata)
        return updated

    def list_tasks(self, actor: UserAccount) -> tuple[TicketRecord, ...]:
        self._require(actor, Permission.ANALYST_WORK)
        tasks = tuple(
            ticket
            for ticket in self._tickets.tickets.list_workflow_tickets(
                actor, ANALYST_READ_PERMISSIONS
            )
            if assigned_to(ticket, actor.user_id)
            and ticket.state in {*ACTIVE_ANALYST_STATES, TicketState.QC_REVIEW}
        )
        return tasks[:ANALYST_TASK_LIST_LIMIT]

    def task_details(self, actor: UserAccount, ticket_id: UUID) -> TicketRecord:
        self._require(actor, Permission.ANALYST_WORK)
        ticket = self._tickets.tickets.get_workflow_ticket(
            actor, ticket_id, ANALYST_READ_PERMISSIONS
        )
        if not assigned_to(ticket, actor.user_id):
            raise AppError(404, "task_not_found", "Analyst task was not found.")
        return ticket

    def visible_linked_products(
        self, actor: UserAccount, ticket: TicketRecord
    ) -> tuple[LinkedAnalystProduct, ...]:
        """Return only links whose product is readable under the actor's current policy."""
        visible: list[LinkedAnalystProduct] = []
        for link in ticket.linked_products[:ANALYST_LINKED_PRODUCT_LIMIT]:
            try:
                self._store.details.get_visible_product(actor, link.product_id)
            except AppError:
                continue
            visible.append(link)
        return tuple(visible)

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
        self._record_audit_or_rollback(
            ticket,
            "analyst_note_added",
            actor,
            {"ticket_id": str(ticket_id)},
        )
        return updated

    def link_product(self, actor: UserAccount, ticket_id: UUID, product_id: UUID) -> TicketRecord:
        ticket = self._active_task(actor, ticket_id)
        if len(ticket.linked_products) >= ANALYST_LINKED_PRODUCT_LIMIT:
            raise AppError(
                409,
                "linked_product_limit_reached",
                "The analyst task has reached its linked-product limit.",
            )
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
        self._record_audit_or_rollback(
            ticket,
            "analyst_product_linked",
            actor,
            {"ticket_id": str(ticket_id), "product_id": str(product_id)},
        )
        return updated

    def update_work_package(
        self, actor: UserAccount, ticket_id: UUID, package_id: UUID, status: WorkPackageStatus
    ) -> TicketRecord:
        ticket = self._active_task(actor, ticket_id)
        target = next(
            (package for package in ticket.work_packages if package.package_id == package_id),
            None,
        )
        if target is None:
            raise AppError(404, "work_package_not_found", "Work package was not found.")
        if target.status == status:
            # Setting the current status again is a successful no-op.
            return ticket
        packages = tuple(
            replace(package, status=status) if package.package_id == package_id else package
            for package in ticket.work_packages
        )
        updated = self._tickets.tickets.save_system_update(
            replace(
                ticket,
                work_packages=packages,
                timeline=(
                    *ticket.timeline,
                    timeline(ticket.ticket_id, actor.user_id, "work_package_updated", status.value),
                ),
            )
        )
        self._record_audit_or_rollback(
            ticket,
            "work_package_updated",
            actor,
            {
                "ticket_id": str(ticket_id),
                "package_id": str(package_id),
                "status": status.value,
            },
        )
        return updated

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
        self._record_audit_or_rollback(
            ticket,
            "draft_product_saved",
            actor,
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
        self._record_audit_or_rollback(
            ticket, "submitted_to_qc", actor, {"ticket_id": str(ticket_id)}
        )
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

    def _record_audit_or_rollback(
        self,
        original_ticket: TicketRecord,
        event_type: str,
        actor: UserAccount,
        details: dict[str, str],
    ) -> None:
        record_ticket_audit_or_rollback(
            self._tickets.tickets, self._audit_log, original_ticket, event_type, actor, details
        )

    @staticmethod
    def _ensure_transition(current: TicketState, target: TicketState) -> None:
        if not can_transition(current, target):
            raise AppError(409, "invalid_ticket_state", "Ticket cannot move to that state.")
