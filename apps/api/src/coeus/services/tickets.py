from dataclasses import dataclass, replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

from coeus.core.errors import AppError
from coeus.core.permissions import Permission
from coeus.domain.auth import UserAccount
from coeus.domain.enums import TicketState
from coeus.domain.state_machine import can_transition
from coeus.domain.tickets import (
    AgentRun,
    AgentRunStatus,
    AttachmentMetadata,
    ChatMessage,
    IntakeDetails,
    MessageAuthor,
    TicketRecord,
    TicketTimelineEntry,
)
from coeus.repositories.tickets import InMemoryTicketRepository
from coeus.services.audit import AuditLog
from coeus.services.intake import (
    IntakeExtractionService,
    MockLlmProvider,
    RequirementCompletenessService,
    merge_intake,
)


@dataclass(frozen=True)
class TicketServices:
    tickets: "TicketService"
    conversations: "ConversationService"


class TicketService:
    def __init__(
        self,
        repository: InMemoryTicketRepository,
        completeness: RequirementCompletenessService,
        audit_log: AuditLog,
    ) -> None:
        self._repository = repository
        self._completeness = completeness
        self._audit_log = audit_log

    def list_visible_tickets(self, actor: UserAccount) -> tuple[TicketRecord, ...]:
        if Permission.TICKET_READ_ALL in actor.permissions:
            return self._repository.list_tickets()
        if Permission.TICKET_READ_ASSIGNED in actor.permissions:
            return tuple(
                ticket
                for ticket in self._repository.list_tickets()
                if ticket.state == TicketState.RFI_SEARCHING
            )
        if Permission.TICKET_READ_OWN in actor.permissions:
            return self._repository.list_for_requester(actor.user_id)
        return ()

    def get_visible_ticket(self, actor: UserAccount, ticket_id: UUID) -> TicketRecord:
        ticket = self._repository.get(ticket_id)
        if ticket is None or not self._can_read(actor, ticket):
            raise AppError(404, "ticket_not_found", "Ticket was not found.")
        return ticket

    def update_intake(
        self, actor: UserAccount, ticket_id: UUID, updates: dict[str, str]
    ) -> TicketRecord:
        ticket = self.get_editable_ticket(actor, ticket_id)
        intake = merge_intake(ticket.intake, updates)
        intake = self._completeness.with_completeness(intake)
        state = self._state_for_intake(ticket.state, intake)
        updated = self._save(
            replace(
                ticket,
                intake=intake,
                state=state,
                timeline=(
                    *ticket.timeline,
                    _timeline(ticket.ticket_id, actor.user_id, "intake_updated", "Intake updated."),
                ),
            )
        )
        self._audit_log.record(
            "ticket_intake_updated",
            actor_user_id=str(actor.user_id),
            metadata={"ticket_id": str(ticket.ticket_id)},
        )
        return updated

    def add_attachment(
        self,
        actor: UserAccount,
        ticket_id: UUID,
        name: str,
        description: str,
        source_type: str,
    ) -> TicketRecord:
        ticket = self.get_editable_ticket(actor, ticket_id)
        attachment = AttachmentMetadata(
            attachment_id=uuid4(),
            ticket_id=ticket.ticket_id,
            name=name,
            description=description,
            source_type=source_type,
            created_at=datetime.now(UTC),
        )
        return self._save(
            replace(
                ticket,
                attachments=(*ticket.attachments, attachment),
                timeline=(
                    *ticket.timeline,
                    _timeline(ticket.ticket_id, actor.user_id, "attachment_added", name),
                ),
            )
        )

    def submit(self, actor: UserAccount, ticket_id: UUID) -> TicketRecord:
        ticket = self.get_editable_ticket(actor, ticket_id)
        if not self._completeness.is_complete_enough(ticket.intake):
            raise AppError(409, "intake_incomplete", "Complete the required intake fields first.")
        if not can_transition(ticket.state, TicketState.RFI_SEARCHING):
            raise AppError(
                409, "invalid_ticket_state", "Ticket cannot be submitted from this state."
            )
        project_name = _suggest_project_name(ticket.intake)
        search_run = AgentRun(
            run_id=uuid4(),
            ticket_id=ticket.ticket_id,
            agent_name="rfi-search",
            status=AgentRunStatus.QUEUED,
            summary="Controlled search queued after intake completion.",
            safety_flags=(),
            created_at=datetime.now(UTC),
        )
        updated = self._save(
            replace(
                ticket,
                state=TicketState.RFI_SEARCHING,
                suggested_project_name=project_name,
                agent_runs=(*ticket.agent_runs, search_run),
                timeline=(
                    *ticket.timeline,
                    _timeline(
                        ticket.ticket_id, actor.user_id, "ticket_submitted", "Ticket submitted."
                    ),
                    _timeline(ticket.ticket_id, actor.user_id, "search_started", "Search queued."),
                ),
            )
        )
        self._audit_log.record(
            "ticket_submitted",
            actor_user_id=str(actor.user_id),
            metadata={"ticket_id": str(ticket.ticket_id)},
        )
        return updated

    def add_information(self, actor: UserAccount, ticket_id: UUID, body: str) -> TicketRecord:
        ticket = self.get_visible_ticket(actor, ticket_id)
        if (
            not _is_owner(actor, ticket)
            or Permission.TICKET_ADD_INFORMATION not in actor.permissions
        ):
            raise AppError(404, "ticket_not_found", "Ticket was not found.")
        return self._save(
            replace(
                ticket,
                timeline=(
                    *ticket.timeline,
                    _timeline(ticket.ticket_id, actor.user_id, "information_added", body),
                ),
            )
        )

    def get_editable_ticket(self, actor: UserAccount, ticket_id: UUID) -> TicketRecord:
        ticket = self.get_visible_ticket(actor, ticket_id)
        if not _is_owner(actor, ticket) and Permission.TICKET_READ_ALL not in actor.permissions:
            raise AppError(404, "ticket_not_found", "Ticket was not found.")
        if ticket.state not in {TicketState.DRAFT_INTAKE, TicketState.INFO_REQUIRED}:
            raise AppError(409, "ticket_not_editable", "Ticket intake is no longer editable.")
        return ticket

    def _save(self, ticket: TicketRecord) -> TicketRecord:
        updated = replace(ticket, updated_at=datetime.now(UTC))
        self._repository.save(updated)
        return updated

    def _can_read(self, actor: UserAccount, ticket: TicketRecord) -> bool:
        return (
            _is_owner(actor, ticket)
            or Permission.TICKET_READ_ALL in actor.permissions
            or (
                Permission.TICKET_READ_ASSIGNED in actor.permissions
                and ticket.state == TicketState.RFI_SEARCHING
            )
        )

    def _state_for_intake(self, current: TicketState, intake: IntakeDetails) -> TicketState:
        target = (
            TicketState.DRAFT_INTAKE
            if self._completeness.is_complete_enough(intake)
            else TicketState.INFO_REQUIRED
        )
        if current == target:
            return current
        if can_transition(current, target):
            return target
        return current


class ConversationService:
    def __init__(
        self,
        repository: InMemoryTicketRepository,
        tickets: TicketService,
        extractor: IntakeExtractionService,
        llm_provider: MockLlmProvider,
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
        user_message = _message(ticket.ticket_id, MessageAuthor.USER, message)
        safety_flags = self._extractor.safety_flags_for(message)
        intake = self._extractor.extract(message, ticket.intake)
        assistant_message = _message(
            ticket.ticket_id,
            MessageAuthor.ASSISTANT,
            self._llm_provider.build_assistant_message(intake, safety_flags),
        )
        agent_run = AgentRun(
            run_id=uuid4(),
            ticket_id=ticket.ticket_id,
            agent_name="intake-extraction",
            status=AgentRunStatus.COMPLETED,
            summary="Structured intake fields extracted from user chat.",
            safety_flags=safety_flags,
            created_at=datetime.now(UTC),
        )
        state = self._tickets._state_for_intake(ticket.state, intake)
        updated = self._tickets._save(
            replace(
                ticket,
                state=state,
                intake=intake,
                messages=(*ticket.messages, user_message, assistant_message),
                agent_runs=(*ticket.agent_runs, agent_run),
                timeline=(
                    *ticket.timeline,
                    _timeline(
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
        ticket = TicketRecord(
            ticket_id=ticket_id,
            reference=self._repository.next_reference(),
            requester_user_id=actor.user_id,
            state=TicketState.DRAFT_INTAKE,
            intake=IntakeDetails(),
            timeline=(
                _timeline(ticket_id, actor.user_id, "ticket_created", "Draft intake started."),
            ),
        )
        self._repository.save(ticket)
        return ticket


def build_ticket_services(audit_log: AuditLog) -> TicketServices:
    repository = InMemoryTicketRepository()
    completeness = RequirementCompletenessService()
    tickets = TicketService(repository, completeness, audit_log)
    conversations = ConversationService(
        repository,
        tickets,
        IntakeExtractionService(),
        MockLlmProvider(),
        audit_log,
    )
    return TicketServices(tickets=tickets, conversations=conversations)


def _message(ticket_id: UUID, author: MessageAuthor, body: str) -> ChatMessage:
    return ChatMessage(
        message_id=uuid4(),
        ticket_id=ticket_id,
        author=author,
        body=body,
        created_at=datetime.now(UTC),
    )


def _timeline(
    ticket_id: UUID, actor_user_id: UUID, event_type: str, body: str
) -> TicketTimelineEntry:
    return TicketTimelineEntry(
        entry_id=uuid4(),
        ticket_id=ticket_id,
        event_type=event_type,
        body=body,
        actor_user_id=actor_user_id,
        created_at=datetime.now(UTC),
    )


def _suggest_project_name(intake: IntakeDetails) -> str:
    return f"{intake.title or 'Draft Requirement'} Workspace"


def _is_owner(actor: UserAccount, ticket: TicketRecord) -> bool:
    return ticket.requester_user_id == actor.user_id
