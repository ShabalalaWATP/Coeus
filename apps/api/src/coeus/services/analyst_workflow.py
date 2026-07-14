from dataclasses import replace
from uuid import UUID

from coeus.core.errors import AppError
from coeus.core.permissions import Permission
from coeus.domain.access import ProductStatus
from coeus.domain.auth import UserAccount
from coeus.domain.draft_audience import DraftAudienceReason
from coeus.domain.enums import TicketState
from coeus.domain.qc import QcDecisionStatus
from coeus.domain.state_machine import can_transition
from coeus.domain.tickets import (
    AnalystNote,
    LinkedAnalystProduct,
    TicketRecord,
    WorkPackageStatus,
)
from coeus.services.analyst_drafts import (
    DraftProductInput,
    draft_asset,
    ensure_draft_budget,
    new_uuid,
    now,
)
from coeus.services.analyst_records import (
    all_work_packages_complete,
    assigned_to,
    draft_version,
    linked_product_record,
    next_draft_version,
)
from coeus.services.audit import AuditLog
from coeus.services.prioritisation import priority_sort_key
from coeus.services.store import StoreServices
from coeus.services.ticket_records import timeline
from coeus.services.tickets import TicketServices

ACTIVE_ANALYST_STATES = {TicketState.ANALYST_IN_PROGRESS, TicketState.REWORK_REQUIRED}
VISIBLE_ANALYST_STATES = {
    *ACTIVE_ANALYST_STATES,
    TicketState.MANAGER_APPROVAL,
    TicketState.QC_REVIEW,
}
ANALYST_READ_PERMISSIONS = frozenset({Permission.ANALYST_WORK})
ANALYST_TASK_LIST_LIMIT = 100
ANALYST_LINKED_PRODUCT_LIMIT = 25


class AnalystWorkflowService:
    def __init__(
        self,
        tickets: TicketServices,
        store: StoreServices,
        audit_log: AuditLog,
    ) -> None:
        self._tickets = tickets
        self._store = store
        self._audit_log = audit_log

    def list_tasks(self, actor: UserAccount) -> tuple[TicketRecord, ...]:
        self._require(actor, Permission.ANALYST_WORK)
        tasks = (
            ticket
            for ticket in self._tickets.tickets.list_workflow_tickets(
                actor, ANALYST_READ_PERMISSIONS
            )
            if assigned_to(ticket, actor.user_id) and ticket.state in VISIBLE_ANALYST_STATES
        )
        return tuple(sorted(tasks, key=priority_sort_key))[:ANALYST_TASK_LIST_LIMIT]

    def task_details(self, actor: UserAccount, ticket_id: UUID) -> TicketRecord:
        self._require(actor, Permission.ANALYST_WORK)
        ticket = self._tickets.tickets.get_workflow_ticket(
            actor, ticket_id, ANALYST_READ_PERMISSIONS
        )
        if not assigned_to(ticket, actor.user_id) or ticket.state not in VISIBLE_ANALYST_STATES:
            raise AppError(404, "task_not_found", "Analyst task was not found.")
        return ticket

    def visible_linked_products(
        self, actor: UserAccount, ticket: TicketRecord
    ) -> tuple[LinkedAnalystProduct, ...]:
        """Return only links whose product is readable under the actor's current policy."""
        visible: list[LinkedAnalystProduct] = []
        for link in ticket.linked_products[:ANALYST_LINKED_PRODUCT_LIMIT]:
            try:
                self._store.details.get_workflow_visible_product(
                    actor,
                    link.product_id,
                    DraftAudienceReason.ASSIGNED_ANALYST,
                    require_projection=True,
                )
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
        return self._tickets.mutations.save_audited_if_current(
            ticket,
            replace(
                ticket,
                analyst_notes=(*ticket.analyst_notes, note),
                timeline=(
                    *ticket.timeline,
                    timeline(ticket.ticket_id, actor.user_id, "analyst_note_added", body),
                ),
            ),
            "analyst_note_added",
            actor,
            {"ticket_id": str(ticket_id)},
        )

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
        if product.metadata.status is not ProductStatus.PUBLISHED:
            raise AppError(404, "product_not_found", "Product was not found.")
        link = linked_product_record(
            ticket.ticket_id,
            product.product_id,
            product.reference,
            product.metadata.title,
            product.metadata.summary,
            actor.user_id,
        )
        return self._tickets.mutations.save_audited_if_current(
            ticket,
            replace(
                ticket,
                linked_products=(*ticket.linked_products, link),
                timeline=(
                    *ticket.timeline,
                    timeline(ticket.ticket_id, actor.user_id, "analyst_product_linked", link.title),
                ),
            ),
            "analyst_product_linked",
            actor,
            {"ticket_id": str(ticket_id), "product_id": str(product_id)},
        )

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
        return self._tickets.mutations.save_audited_if_current(
            ticket,
            replace(
                ticket,
                work_packages=packages,
                timeline=(
                    *ticket.timeline,
                    timeline(ticket.ticket_id, actor.user_id, "work_package_updated", status.value),
                ),
            ),
            "work_package_updated",
            actor,
            {
                "ticket_id": str(ticket_id),
                "package_id": str(package_id),
                "status": status.value,
            },
        )

    def create_draft(
        self, actor: UserAccount, ticket_id: UUID, draft: DraftProductInput
    ) -> TicketRecord:
        ticket = self._active_task(actor, ticket_id)
        ensure_draft_budget(ticket.draft_products, draft)
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
        return self._tickets.mutations.save_audited_if_current(
            ticket,
            replace(
                ticket,
                draft_products=(*ticket.draft_products, version),
                timeline=(
                    *ticket.timeline,
                    timeline(ticket.ticket_id, actor.user_id, "draft_product_saved", draft.title),
                ),
            ),
            "draft_product_saved",
            actor,
            {"ticket_id": str(ticket_id)},
        )

    def submit_work(self, actor: UserAccount, ticket_id: UUID) -> TicketRecord:
        """Submit completed work for review.

        First submissions go to the team manager for approval; QC-requested
        rework returns straight to QC, which asked for the changes.
        """
        self._require(actor, Permission.ANALYST_SUBMIT_PRODUCT)
        ticket = self._active_task(actor, ticket_id)
        if not ticket.draft_products:
            raise AppError(409, "draft_required", "A draft product is required before review.")
        if not all_work_packages_complete(ticket):
            raise AppError(409, "work_packages_incomplete", "Complete work packages before review.")
        rework = ticket.state == TicketState.REWORK_REQUIRED
        if not self._has_revised_draft(ticket):
            raise AppError(
                409,
                "revised_draft_required",
                "Save a revised draft after the latest rework request before resubmitting.",
            )
        target = TicketState.QC_REVIEW if rework else TicketState.MANAGER_APPROVAL
        event_type = "submitted_to_qc" if rework else "submitted_to_manager"
        summary = "Resubmitted to QC." if rework else "Submitted to the team manager."
        self._ensure_transition(ticket.state, target)
        return self._tickets.mutations.save_audited_if_current(
            ticket,
            replace(
                ticket,
                state=target,
                timeline=(
                    *ticket.timeline,
                    timeline(ticket.ticket_id, actor.user_id, event_type, summary),
                ),
            ),
            event_type,
            actor,
            {"ticket_id": str(ticket_id)},
        )

    @staticmethod
    def _has_revised_draft(ticket: TicketRecord) -> bool:
        latest_draft_at = ticket.draft_products[-1].created_at
        markers = [
            decision.created_at
            for decision in ticket.qc_decisions
            if decision.status == QcDecisionStatus.REJECTED
        ]
        markers.extend(
            entry.created_at
            for entry in ticket.timeline
            if entry.event_type == "manager_returned_rework"
        )
        return not markers or latest_draft_at > max(markers)

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
    def _ensure_transition(current: TicketState, target: TicketState) -> None:
        if not can_transition(current, target):
            raise AppError(409, "invalid_ticket_state", "Ticket cannot move to that state.")
