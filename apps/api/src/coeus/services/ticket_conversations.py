from dataclasses import replace
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID, uuid4

from coeus.core.errors import AppError
from coeus.core.resource_limits import (
    MAX_ASSISTANT_REPLY_BYTES,
    MAX_CHAT_HISTORY_BYTES,
    MAX_CHAT_MESSAGES_PER_TICKET,
    text_bytes,
)
from coeus.domain.agent_names import CUSTOMER_CHATBOT_AGENT
from coeus.domain.auth import UserAccount
from coeus.domain.enums import TicketState
from coeus.domain.tickets import (
    AgentRun,
    AgentRunStatus,
    IntakeDetails,
    MessageAuthor,
    TicketRecord,
)
from coeus.repositories.tickets import InMemoryTicketRepository
from coeus.services import conversation_lifecycle as lifecycle
from coeus.services.audit import AuditLog
from coeus.services.intake import IntakeAssistantProvider, IntakeExtractionService
from coeus.services.intake_standard import next_elicitation
from coeus.services.prioritisation import with_assessment
from coeus.services.ticket_records import message as message_record
from coeus.services.ticket_records import timeline


class ConversationTicketService(Protocol):
    def get_editable_ticket(self, actor: UserAccount, ticket_id: UUID) -> TicketRecord:
        pass

    def state_for_intake(self, current_state: TicketState, intake: IntakeDetails) -> TicketState:
        pass

    def save_system_update(self, ticket: TicketRecord) -> TicketRecord:
        pass


class ConversationService:
    def __init__(
        self,
        repository: InMemoryTicketRepository,
        tickets: ConversationTicketService,
        extractor: IntakeExtractionService,
        llm_provider: IntakeAssistantProvider,
        audit_log: AuditLog,
    ) -> None:
        self._repository = repository
        self._tickets = tickets
        self._extractor = extractor
        self._llm_provider = llm_provider
        self._audit_log = audit_log

    def send_message(
        self, actor: UserAccount, message: str, ticket_id: UUID | None = None
    ) -> TicketRecord:
        ticket = (
            self._tickets.get_editable_ticket(actor, ticket_id)
            if ticket_id
            else self._create(actor)
        )
        if ticket.conversation_status == lifecycle.CONVERSATION_CLOSED:
            raise AppError(
                409,
                "conversation_closed",
                "The intake conversation is complete. Review the details and submit.",
            )
        self._ensure_chat_budget(ticket, message)
        user_message = message_record(ticket.ticket_id, MessageAuthor.USER, message)
        safety_flags = self._extractor.safety_flags_for(message)
        # Flagged messages are never extracted, so injected text cannot land
        # in intake fields; the message, flags and refusal are still recorded.
        intake = ticket.intake if safety_flags else self._extractor.extract(message, ticket.intake)
        if safety_flags:
            reply = self._llm_provider.build_assistant_message(intake, safety_flags)
            conversation_status = ticket.conversation_status
        else:
            reply, conversation_status = self._reply_and_status(
                ticket.conversation_status, message, intake
            )
        assistant_message = message_record(ticket.ticket_id, MessageAuthor.ASSISTANT, reply)
        if self._chat_bytes(ticket) + text_bytes(message, reply) > MAX_CHAT_HISTORY_BYTES:
            raise AppError(409, "chat_history_limit_reached", "The chat history limit was reached.")
        agent_run = AgentRun(
            run_id=uuid4(),
            ticket_id=ticket.ticket_id,
            agent_name=CUSTOMER_CHATBOT_AGENT,
            status=AgentRunStatus.COMPLETED,
            summary=(
                "Message flagged; intake extraction skipped."
                if safety_flags
                else "Structured intake fields extracted from user chat."
            ),
            safety_flags=safety_flags,
            created_at=datetime.now(UTC),
        )
        state = self._tickets.state_for_intake(ticket.state, intake)
        updated = self._tickets.save_system_update(
            with_assessment(
                replace(
                    ticket,
                    state=state,
                    intake=intake,
                    conversation_status=conversation_status,
                    messages=(*ticket.messages, user_message, assistant_message),
                    agent_runs=(*ticket.agent_runs, agent_run),
                    timeline=(
                        *ticket.timeline,
                        timeline(
                            ticket.ticket_id, actor.user_id, "chat_message", "User chat received."
                        ),
                    ),
                )
            )
        )
        self._audit_log.record(
            "ticket_chat_message_received",
            actor_user_id=str(actor.user_id),
            metadata={"ticket_id": str(ticket.ticket_id)},
        )
        return updated

    @staticmethod
    def _chat_bytes(ticket: TicketRecord) -> int:
        return sum(text_bytes(item.body) for item in ticket.messages)

    def _ensure_chat_budget(self, ticket: TicketRecord, message: str) -> None:
        if len(ticket.messages) + 2 > MAX_CHAT_MESSAGES_PER_TICKET:
            raise AppError(409, "chat_history_limit_reached", "The chat history limit was reached.")
        projected = self._chat_bytes(ticket) + text_bytes(message) + MAX_ASSISTANT_REPLY_BYTES
        if projected > MAX_CHAT_HISTORY_BYTES:
            raise AppError(409, "chat_history_limit_reached", "The chat history limit was reached.")

    def _reply_and_status(
        self, status: str, message: str, intake: IntakeDetails
    ) -> tuple[str, str]:
        """Deterministic conversation lifecycle; the LLM never decides this."""
        complete = not intake.missing_information
        offered = status == lifecycle.CONVERSATION_CLOSE_OFFERED
        if offered and complete and lifecycle.confirms_close(message):
            return lifecycle.CLOSED_MESSAGE, lifecycle.CONVERSATION_CLOSED
        if lifecycle.wants_to_end(message):
            if complete:
                return lifecycle.CLOSED_MESSAGE, lifecycle.CONVERSATION_CLOSED
            entry = next_elicitation(intake.missing_information)
            question = entry.question if entry else ""
            return (
                lifecycle.cannot_close_message(question).strip(),
                lifecycle.CONVERSATION_OPEN,
            )
        if complete:
            return lifecycle.CLOSE_OFFER_MESSAGE, lifecycle.CONVERSATION_CLOSE_OFFERED
        return (
            self._llm_provider.build_assistant_message(intake, ()),
            lifecycle.CONVERSATION_OPEN,
        )

    def _create(self, actor: UserAccount) -> TicketRecord:
        ticket_id = uuid4()
        return TicketRecord(
            ticket_id=ticket_id,
            reference=self._repository.next_reference(),
            requester_user_id=actor.user_id,
            state=TicketState.DRAFT_INTAKE,
            intake=IntakeDetails(),
            timeline=(
                timeline(ticket_id, actor.user_id, "ticket_created", "Draft intake started."),
            ),
        )
