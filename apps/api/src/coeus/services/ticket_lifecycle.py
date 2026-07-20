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
        return self._save_and_audit(
            ticket,
            replace(
                ticket,
                state=TicketState.CANCELLED,
                timeline=(
                    *ticket.timeline,
                    timeline(ticket.ticket_id, actor.user_id, "ticket_cancelled", reason),
                ),
            ),
            "ticket_cancelled",
            actor,
        )

    def no_match_consent(
        self, actor: UserAccount, ticket_id: UUID, task_as_new_request: bool
    ) -> TicketRecord:
        """Record the requester decision after all discovery options are resolved."""
        ticket = self._tickets.get_visible_ticket(actor, ticket_id)
        if not is_owner(actor, ticket):
            raise AppError(403, "forbidden", "Only the requester can decide new tasking.")
        if ticket.state not in {TicketState.RFI_NO_MATCH, TicketState.NEW_TASKING_CONSENT}:
            raise AppError(
                409, "invalid_ticket_state", "This request is not awaiting tasking consent."
            )
        target_state = (
            TicketState.JIOC_ROUTING_PENDING
            if task_as_new_request
            else TicketState.CLOSED_UNANSWERED
        )
        if not can_transition(ticket.state, target_state):
            raise AppError(409, "invalid_ticket_state", "This request cannot be updated.")
        event_type = "tasking_confirmed" if task_as_new_request else "tasking_declined"
        body = (
            "Requester confirmed new tasking; queued for JIOC routing."
            if task_as_new_request
            else "The search did not answer the question and the requester declined new tasking."
        )
        return self._save_and_audit(
            ticket,
            replace(
                ticket,
                state=target_state,
                timeline=(
                    *ticket.timeline,
                    timeline(ticket.ticket_id, actor.user_id, event_type, body),
                ),
            ),
            "no_match_tasking_confirmed" if task_as_new_request else "no_match_tasking_declined",
            actor,
        )

    def collect_choice(self, actor: UserAccount, ticket_id: UUID, analysed: bool) -> TicketRecord:
        """Record whether the requester wants raw collect or collect plus analysis."""
        ticket = self._tickets.get_visible_ticket(actor, ticket_id)
        if not is_owner(actor, ticket):
            raise AppError(403, "forbidden", "Only the requester can choose the collect option.")
        if ticket.state != TicketState.COLLECT_CHOICE or not can_transition(
            ticket.state, TicketState.ANALYST_ASSIGNMENT
        ):
            raise AppError(
                409, "invalid_ticket_state", "This request is not awaiting a collect choice."
            )
        disposition = "analysed" if analysed else "raw"
        body = (
            "Requester chose collect followed by RFA analysis."
            if analysed
            else "Requester chose the raw collect only."
        )
        return self._save_and_audit(
            ticket,
            replace(
                ticket,
                state=TicketState.ANALYST_ASSIGNMENT,
                collect_disposition=disposition,
                timeline=(
                    *ticket.timeline,
                    timeline(ticket.ticket_id, actor.user_id, "collect_choice_recorded", body),
                ),
            ),
            f"collect_choice_{disposition}",
            actor,
        )

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
        return self._save_and_audit(
            ticket,
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
            ),
            "ticket_delivery_confirmed",
            actor,
        )

    def _save_and_audit(
        self,
        original_ticket: TicketRecord,
        proposed_ticket: TicketRecord,
        event_type: str,
        actor: UserAccount,
    ) -> TicketRecord:
        return self._tickets.mutations.save_audited_if_current(
            original_ticket,
            proposed_ticket,
            event_type,
            actor,
            {"ticket_id": str(original_ticket.ticket_id)},
        )
