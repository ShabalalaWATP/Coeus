from dataclasses import replace
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID, uuid4

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
from coeus.services.audit import AuditLog
from coeus.services.intake import IntakeAssistantProvider, IntakeExtractionService
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
        user_message = message_record(ticket.ticket_id, MessageAuthor.USER, message)
        safety_flags = self._extractor.safety_flags_for(message)
        # Flagged messages are never extracted, so injected text cannot land
        # in intake fields; the message, flags and refusal are still recorded.
        intake = ticket.intake if safety_flags else self._extractor.extract(message, ticket.intake)
        assistant_message = message_record(
            ticket.ticket_id,
            MessageAuthor.ASSISTANT,
            self._llm_provider.build_assistant_message(intake, safety_flags),
        )
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
            replace(
                ticket,
                state=state,
                intake=intake,
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
        self._audit_log.record(
            "ticket_chat_message_received",
            actor_user_id=str(actor.user_id),
            metadata={"ticket_id": str(ticket.ticket_id)},
        )
        return updated

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
