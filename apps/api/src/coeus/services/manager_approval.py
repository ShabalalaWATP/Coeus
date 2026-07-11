"""Team manager approval of completed analyst work.

Analysts submit finished work to their team manager. The manager either
forwards it to Quality Control or returns it to the analysts for rework.
Separation of duties: a manager who drafted or holds an active assignment on
the ticket cannot approve it.
"""

from dataclasses import replace
from uuid import UUID

from coeus.core.errors import AppError
from coeus.core.permissions import Permission
from coeus.domain.auth import UserAccount
from coeus.domain.enums import TicketState
from coeus.domain.state_machine import can_transition
from coeus.domain.tickets import RoutingRoute, TicketRecord
from coeus.services.analyst_records import approved_route, assigned_analyst_ids
from coeus.services.audit import AuditLog
from coeus.services.audit_rollback import record_ticket_audit_or_rollback
from coeus.services.ticket_records import timeline
from coeus.services.tickets import TicketServices

APPROVAL_READ_PERMISSIONS = frozenset({Permission.RFA_REVIEW, Permission.COLLECTION_REVIEW})
ROUTE_PERMISSIONS: dict[RoutingRoute, Permission] = {
    RoutingRoute.RFA: Permission.RFA_REVIEW,
    RoutingRoute.CM: Permission.COLLECTION_REVIEW,
}


class ManagerApprovalService:
    def __init__(self, tickets: TicketServices, audit_log: AuditLog) -> None:
        self._tickets = tickets
        self._audit_log = audit_log

    def approve(self, actor: UserAccount, ticket_id: UUID) -> TicketRecord:
        ticket = self._reviewable_ticket(actor, ticket_id)
        self._ensure_separation_of_duties(actor, ticket)
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
                        "manager_approved",
                        "Manager approved the work and forwarded it to Quality Control.",
                    ),
                ),
            )
        )
        record_ticket_audit_or_rollback(
            self._tickets.tickets,
            self._audit_log,
            ticket,
            "manager_approved",
            actor,
            {"ticket_id": str(ticket_id)},
        )
        return updated

    def return_for_rework(self, actor: UserAccount, ticket_id: UUID, reason: str) -> TicketRecord:
        cleaned = reason.strip()
        if len(cleaned) < 3:
            raise AppError(422, "reason_required", "A rework reason is required.")
        ticket = self._reviewable_ticket(actor, ticket_id)
        self._ensure_transition(ticket.state, TicketState.ANALYST_IN_PROGRESS)
        updated = self._tickets.tickets.save_system_update(
            replace(
                ticket,
                state=TicketState.ANALYST_IN_PROGRESS,
                timeline=(
                    *ticket.timeline,
                    timeline(ticket.ticket_id, actor.user_id, "manager_returned_rework", cleaned),
                ),
            )
        )
        record_ticket_audit_or_rollback(
            self._tickets.tickets,
            self._audit_log,
            ticket,
            "manager_returned_rework",
            actor,
            {"ticket_id": str(ticket_id)},
        )
        return updated

    def review_work(self, actor: UserAccount, ticket_id: UUID) -> TicketRecord:
        """Return the submitted work only to the manager authorised to decide it."""
        return self._reviewable_ticket(actor, ticket_id)

    def _reviewable_ticket(self, actor: UserAccount, ticket_id: UUID) -> TicketRecord:
        if Permission.PRODUCT_APPROVE not in actor.permissions:
            raise AppError(403, "forbidden", "Permission denied.")
        ticket = self._tickets.tickets.get_workflow_ticket(
            actor, ticket_id, APPROVAL_READ_PERMISSIONS
        )
        if ticket.state != TicketState.MANAGER_APPROVAL:
            raise AppError(409, "invalid_ticket_state", "Ticket is not awaiting manager approval.")
        route = approved_route(ticket)
        permission = ROUTE_PERMISSIONS.get(route) if route is not None else None
        if permission is None or permission not in actor.permissions:
            raise AppError(403, "forbidden", "Permission denied.")
        return ticket

    @staticmethod
    def _ensure_separation_of_duties(actor: UserAccount, ticket: TicketRecord) -> None:
        drafted = any(draft.created_by_user_id == actor.user_id for draft in ticket.draft_products)
        if drafted or actor.user_id in assigned_analyst_ids(ticket):
            raise AppError(403, "separation_of_duties", "Reviewers cannot approve their own work.")

    @staticmethod
    def _ensure_transition(current: TicketState, target: TicketState) -> None:
        if not can_transition(current, target):
            raise AppError(409, "invalid_ticket_state", "Ticket cannot move to that state.")
