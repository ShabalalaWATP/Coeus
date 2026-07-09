from dataclasses import replace
from uuid import UUID

from coeus.core.errors import AppError
from coeus.domain.auth import UserAccount
from coeus.domain.enums import TicketState
from coeus.domain.state_machine import can_transition
from coeus.domain.tickets import TicketRecord
from coeus.services.audit import AuditLog
from coeus.services.ticket_records import is_owner, timeline
from coeus.services.tickets import TicketService


class TicketLifecycleService:
    """Requester-driven lifecycle actions that sit outside the intake flow."""

    def __init__(self, tickets: TicketService, audit_log: AuditLog) -> None:
        self._tickets = tickets
        self._audit_log = audit_log

    def cancel(self, actor: UserAccount, ticket_id: UUID, reason: str) -> TicketRecord:
        ticket = self._tickets.get_visible_ticket(actor, ticket_id)
        if not is_owner(actor, ticket):
            raise AppError(403, "forbidden", "Only the requester can cancel this request.")
        if not can_transition(ticket.state, TicketState.CANCELLED):
            raise AppError(409, "invalid_ticket_state", "This request can no longer be cancelled.")
        updated = self._tickets.save_system_update(
            replace(
                ticket,
                state=TicketState.CANCELLED,
                timeline=(
                    *ticket.timeline,
                    timeline(ticket.ticket_id, actor.user_id, "ticket_cancelled", reason),
                ),
            )
        )
        self._record_ticket_audit_or_rollback(ticket, "ticket_cancelled", actor)
        return updated

    def no_match_consent(
        self, actor: UserAccount, ticket_id: UUID, task_as_new_request: bool
    ) -> TicketRecord:
        """Record the requester decision after RFI search finds no product match."""
        ticket = self._tickets.get_visible_ticket(actor, ticket_id)
        if not is_owner(actor, ticket):
            raise AppError(403, "forbidden", "Only the requester can decide new tasking.")
        if ticket.state != TicketState.RFI_NO_MATCH:
            raise AppError(
                409, "invalid_ticket_state", "This request is not awaiting no-match consent."
            )
        target_state = (
            TicketState.ROUTE_ASSESSMENT if task_as_new_request else TicketState.CANCELLED
        )
        if not can_transition(ticket.state, target_state):
            raise AppError(409, "invalid_ticket_state", "This request cannot be updated.")
        event_type = "tasking_confirmed" if task_as_new_request else "tasking_declined"
        body = (
            "Requester confirmed tasking as a new request."
            if task_as_new_request
            else "customer declined tasking after no-match"
        )
        updated = self._tickets.save_system_update(
            replace(
                ticket,
                state=target_state,
                timeline=(
                    *ticket.timeline,
                    timeline(ticket.ticket_id, actor.user_id, event_type, body),
                ),
            )
        )
        self._record_ticket_audit_or_rollback(
            ticket,
            "no_match_tasking_confirmed" if task_as_new_request else "no_match_tasking_declined",
            actor,
        )
        return updated

    def confirm_delivery(self, actor: UserAccount, ticket_id: UUID) -> TicketRecord:
        """Requester confirms receipt of the released product, closing the ticket."""
        ticket = self._tickets.get_visible_ticket(actor, ticket_id)
        if not is_owner(actor, ticket):
            raise AppError(403, "forbidden", "Only the requester can confirm delivery.")
        if ticket.state != TicketState.DISSEMINATION_READY or not can_transition(
            ticket.state, TicketState.CLOSED_DELIVERED
        ):
            raise AppError(
                409, "invalid_ticket_state", "This request is not awaiting delivery confirmation."
            )
        updated = self._tickets.save_system_update(
            replace(
                ticket,
                state=TicketState.CLOSED_DELIVERED,
                timeline=(
                    *ticket.timeline,
                    timeline(
                        ticket.ticket_id,
                        actor.user_id,
                        "delivery_confirmed",
                        "Requester confirmed receipt and closed the request.",
                    ),
                ),
            )
        )
        self._record_ticket_audit_or_rollback(ticket, "ticket_delivery_confirmed", actor)
        return updated

    def _record_ticket_audit_or_rollback(
        self, original_ticket: TicketRecord, event_type: str, actor: UserAccount
    ) -> None:
        try:
            self._audit_log.record(
                event_type,
                str(actor.user_id),
                {"ticket_id": str(original_ticket.ticket_id)},
            )
        except Exception:
            self._tickets.save_system_update(original_ticket)
            raise
