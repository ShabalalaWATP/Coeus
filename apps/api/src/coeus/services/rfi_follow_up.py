"""Requester feedback and refined-search preparation after rejected RFI offers."""

from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

from coeus.core.errors import AppError
from coeus.core.resource_limits import (
    MAX_ASSISTANT_REPLY_BYTES,
    MAX_CHAT_HISTORY_BYTES,
    MAX_CHAT_MESSAGES_PER_TICKET,
)
from coeus.domain.agent_names import RFI_SEARCH_AGENT
from coeus.domain.auth import UserAccount
from coeus.domain.enums import TicketState
from coeus.domain.search_metrics import RfiSearchMetrics
from coeus.domain.tickets import (
    AgentRun,
    AgentRunStatus,
    MessageAuthor,
    ProductOffer,
    TicketRecord,
)
from coeus.services import conversation_lifecycle as conversation
from coeus.services.conversation_chat_budget import ensure_chat_budget
from coeus.services.rfi_records import complete_agent_run, timeline
from coeus.services.ticket_mutations import TicketMutationService
from coeus.services.ticket_records import is_owner
from coeus.services.ticket_records import message as message_record
from coeus.services.tickets import TicketService

FEEDBACK_REQUEST = (
    "Thanks for reviewing those products. In a short sentence, what was missing "
    "or needs to be more specific?"
)
FEEDBACK_REPLY = (
    "Thank you. I can search again using that detail, send the requirement to the JIOC "
    "Agent for new tasking, or close the request as unfulfilled."
)


class RfiFollowUpService:
    def __init__(self, tickets: TicketService, mutations: TicketMutationService) -> None:
        self._tickets = tickets
        self._mutations = mutations

    def after_rejection(
        self,
        ticket: TicketRecord,
        actor: UserAccount,
        offers: tuple[ProductOffer, ...],
        metric: RfiSearchMetrics,
        next_state: TicketState,
        reason: str,
    ) -> TicketRecord:
        messages = ticket.messages
        conversation_status = ticket.conversation_status
        entries = [timeline(ticket.ticket_id, actor.user_id, "product_offer_rejected", reason)]
        if next_state in {
            TicketState.NEW_TASKING_CONSENT,
            TicketState.RFI_SEARCH_INCOMPLETE,
        } and not self.feedback_pending(ticket):
            ensure_chat_budget(
                ticket,
                FEEDBACK_REQUEST,
                max_messages=MAX_CHAT_MESSAGES_PER_TICKET,
                max_history_bytes=MAX_CHAT_HISTORY_BYTES,
                max_reply_bytes=MAX_ASSISTANT_REPLY_BYTES,
            )
            messages = (
                *messages,
                message_record(ticket.ticket_id, MessageAuthor.ASSISTANT, FEEDBACK_REQUEST),
            )
            conversation_status = conversation.CONVERSATION_OPEN
            entries.append(
                timeline(
                    ticket.ticket_id,
                    actor.user_id,
                    "rfi_search_feedback_requested",
                    "Istari asked what was missing from the rejected product offers.",
                )
            )
        return replace(
            ticket,
            state=next_state,
            conversation_status=conversation_status,
            messages=messages,
            product_offers=offers,
            search_metrics=(*ticket.search_metrics[:-1], metric),
            timeline=(*ticket.timeline, *entries),
        )

    def record_feedback(
        self,
        actor: UserAccount,
        ticket_id: UUID,
        feedback: str,
    ) -> TicketRecord:
        ticket = self._ticket(actor, ticket_id)
        if not self.feedback_pending(ticket):
            raise AppError(
                409,
                "rfi_search_feedback_unavailable",
                "Search feedback is not awaiting a response.",
            )
        value = feedback.strip()
        if len(value) < 3:
            raise AppError(422, "invalid_search_feedback", "Enter a short feedback response.")
        ensure_chat_budget(
            ticket,
            value,
            max_messages=MAX_CHAT_MESSAGES_PER_TICKET,
            max_history_bytes=MAX_CHAT_HISTORY_BYTES,
            max_reply_bytes=MAX_ASSISTANT_REPLY_BYTES,
        )
        proposed = replace(
            ticket,
            conversation_status=conversation.CONVERSATION_CLOSED,
            messages=(
                *ticket.messages,
                message_record(ticket.ticket_id, MessageAuthor.USER, value),
                message_record(ticket.ticket_id, MessageAuthor.ASSISTANT, FEEDBACK_REPLY),
            ),
            timeline=(
                *ticket.timeline,
                timeline(ticket.ticket_id, actor.user_id, "rfi_search_feedback_recorded", value),
            ),
        )
        return self._mutations.save_audited_if_current(
            ticket,
            proposed,
            "rfi_search_feedback_recorded",
            actor,
            {"ticket_id": str(ticket.ticket_id)},
        )

    def prepare_refined_search(self, actor: UserAccount, ticket_id: UUID) -> TicketRecord:
        ticket = self._ticket(actor, ticket_id)
        if not self.refinement_available(ticket):
            raise AppError(
                409,
                "rfi_search_feedback_required",
                "Tell Istari what was missing before searching again.",
            )
        queued_run = AgentRun(
            run_id=uuid4(),
            ticket_id=ticket.ticket_id,
            agent_name=RFI_SEARCH_AGENT,
            status=AgentRunStatus.QUEUED,
            summary="Refined search queued from requester feedback.",
            safety_flags=(),
            created_at=datetime.now(UTC),
        )
        proposed = replace(
            ticket,
            state=TicketState.RFI_SEARCHING,
            agent_runs=(*ticket.agent_runs, queued_run),
            timeline=(
                *ticket.timeline,
                timeline(
                    ticket.ticket_id,
                    actor.user_id,
                    "rfi_refined_search_started",
                    "Istari started another search using the requester's feedback.",
                ),
            ),
        )
        return self._mutations.save_audited_if_current(
            ticket,
            proposed,
            "rfi_refined_search_started",
            actor,
            {"ticket_id": str(ticket.ticket_id)},
        )

    def record_refined_search_incomplete(
        self,
        actor: UserAccount,
        ticket_id: UUID,
        reason: str,
    ) -> TicketRecord:
        ticket = self._tickets.get_visible_ticket(actor, ticket_id)
        if ticket.state != TicketState.RFI_SEARCHING:
            return ticket
        now = datetime.now(UTC)
        summary = "Refined search did not complete. Retry is required."
        agent_runs, run_id = complete_agent_run(ticket, summary, now)
        previous_query = ticket.search_metrics[-1].query if ticket.search_metrics else ""
        metric = RfiSearchMetrics(
            run_id=run_id,
            query=previous_query,
            candidate_count=0,
            offered_count=0,
            rejected_count=0,
            accepted_product_id=None,
            created_at=now,
            degraded_reason=reason,
            outcome="incomplete",
            assurance="assisted",
            coverage_status="partial",
        )
        proposed = replace(
            ticket,
            state=TicketState.RFI_SEARCH_INCOMPLETE,
            agent_runs=agent_runs,
            search_metrics=(*ticket.search_metrics, metric),
            timeline=(
                *ticket.timeline,
                timeline(
                    ticket.ticket_id,
                    actor.user_id,
                    "rfi_search_incomplete",
                    "Refined search did not complete. Retry before deciding on new tasking.",
                ),
            ),
        )
        return self._mutations.save_audited_if_current(
            ticket,
            proposed,
            "rfi_search_incomplete",
            actor,
            {"ticket_id": str(ticket.ticket_id), "reason": reason},
        )

    @classmethod
    def require_standard_retry_available(cls, ticket: TicketRecord) -> None:
        if cls.feedback_pending(ticket):
            raise AppError(
                409,
                "rfi_search_feedback_required",
                "Tell Istari what was missing before searching again.",
            )
        if cls.refinement_available(ticket):
            raise AppError(
                409,
                "rfi_refine_required",
                "Use the refined search action for this feedback.",
            )

    @classmethod
    def feedback_pending(cls, ticket: TicketRecord) -> bool:
        requested, recorded, _ = cls._feedback_indexes(ticket)
        return requested > recorded

    @classmethod
    def feedback_recorded_for_latest_request(cls, ticket: TicketRecord) -> bool:
        requested, recorded, _ = cls._feedback_indexes(ticket)
        return requested >= 0 and recorded > requested

    @classmethod
    def refinement_available(cls, ticket: TicketRecord) -> bool:
        requested, recorded, refined = cls._feedback_indexes(ticket)
        return requested >= 0 and recorded > max(requested, refined)

    @staticmethod
    def _feedback_indexes(ticket: TicketRecord) -> tuple[int, int, int]:
        requested = -1
        recorded = -1
        refined = -1
        for index, entry in enumerate(ticket.timeline):
            if entry.event_type == "rfi_search_feedback_requested":
                requested = index
            elif entry.event_type == "rfi_search_feedback_recorded":
                recorded = index
            elif entry.event_type == "rfi_refined_search_started":
                refined = index
        return requested, recorded, refined

    def _ticket(self, actor: UserAccount, ticket_id: UUID) -> TicketRecord:
        ticket = self._tickets.get_visible_ticket(actor, ticket_id)
        if not is_owner(actor, ticket):
            raise AppError(404, "ticket_not_found", "Ticket was not found.")
        if ticket.state not in {
            TicketState.NEW_TASKING_CONSENT,
            TicketState.RFI_SEARCH_INCOMPLETE,
        }:
            raise AppError(409, "invalid_ticket_state", "This request is not awaiting a decision.")
        return ticket
