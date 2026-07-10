from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from coeus.core.errors import AppError
from coeus.core.permissions import Permission
from coeus.domain.agent_names import RFI_SEARCH_AGENT
from coeus.domain.auth import UserAccount
from coeus.domain.enums import TicketState
from coeus.domain.state_machine import can_transition
from coeus.domain.tickets import (
    AgentRun,
    AgentRunStatus,
    AttachmentMetadata,
    IntakeDetails,
    TicketRecord,
)
from coeus.repositories.tickets import InMemoryTicketRepository
from coeus.services.audit import AuditLog
from coeus.services.intake import (
    RequirementCompletenessService,
    merge_intake,
)
from coeus.services.ticket_records import (
    is_collaborator,
    is_editor,
    is_owner,
    timeline,
)

if TYPE_CHECKING:
    from coeus.services.ticket_conversations import ConversationService


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
        owns = Permission.TICKET_READ_OWN in actor.permissions
        return tuple(
            ticket
            for ticket in self._repository.list_tickets()
            if (owns and is_owner(actor, ticket)) or is_collaborator(actor, ticket)
        )

    def get_visible_ticket(self, actor: UserAccount, ticket_id: UUID) -> TicketRecord:
        ticket = self._repository.get(ticket_id)
        if ticket is None or not self._can_read(actor, ticket):
            raise AppError(404, "ticket_not_found", "Ticket was not found.")
        return ticket

    def list_workflow_tickets(
        self, actor: UserAccount, permissions: frozenset[Permission]
    ) -> tuple[TicketRecord, ...]:
        if Permission.TICKET_READ_ALL in actor.permissions or permissions.intersection(
            actor.permissions
        ):
            return self._repository.list_tickets()
        return ()

    def get_workflow_ticket(
        self, actor: UserAccount, ticket_id: UUID, permissions: frozenset[Permission]
    ) -> TicketRecord:
        ticket = self._repository.get(ticket_id)
        if ticket is None or (
            Permission.TICKET_READ_ALL not in actor.permissions
            and not permissions.intersection(actor.permissions)
        ):
            raise AppError(404, "ticket_not_found", "Ticket was not found.")
        return ticket

    def update_intake(
        self, actor: UserAccount, ticket_id: UUID, updates: dict[str, str]
    ) -> TicketRecord:
        ticket = self.get_editable_ticket(actor, ticket_id)
        intake = merge_intake(ticket.intake, updates)
        intake = self._completeness.with_completeness(intake)
        state = self.state_for_intake(ticket.state, intake)
        updated = self._save(
            replace(
                ticket,
                intake=intake,
                state=state,
                timeline=(
                    *ticket.timeline,
                    timeline(ticket.ticket_id, actor.user_id, "intake_updated", "Intake updated."),
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
                    timeline(ticket.ticket_id, actor.user_id, "attachment_added", name),
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
        search_run = AgentRun(
            run_id=uuid4(),
            ticket_id=ticket.ticket_id,
            agent_name=RFI_SEARCH_AGENT,
            status=AgentRunStatus.QUEUED,
            summary="Controlled search queued after intake completion.",
            safety_flags=(),
            created_at=datetime.now(UTC),
        )
        updated = self._save(
            replace(
                ticket,
                state=TicketState.RFI_SEARCHING,
                agent_runs=(*ticket.agent_runs, search_run),
                timeline=(
                    *ticket.timeline,
                    timeline(
                        ticket.ticket_id, actor.user_id, "ticket_submitted", "Ticket submitted."
                    ),
                    timeline(ticket.ticket_id, actor.user_id, "search_started", "Search queued."),
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
            not is_owner(actor, ticket)
            and not is_editor(actor, ticket)
            and Permission.TICKET_WRITE_ALL not in actor.permissions
        ) or Permission.TICKET_ADD_INFORMATION not in actor.permissions:
            raise AppError(404, "ticket_not_found", "Ticket was not found.")
        state = (
            TicketState.ROUTE_ASSESSMENT
            if ticket.state == TicketState.INFO_REQUIRED and ticket.route_recommendations
            else ticket.state
        )
        entries = (
            *ticket.timeline,
            timeline(ticket.ticket_id, actor.user_id, "information_added", body),
        )
        if state == TicketState.ROUTE_ASSESSMENT:
            entries = (
                *entries,
                timeline(
                    ticket.ticket_id,
                    actor.user_id,
                    "route_assessment_resumed",
                    "Requester clarification received.",
                ),
            )
        return self._save(
            replace(
                ticket,
                state=state,
                timeline=entries,
            )
        )

    def get_editable_ticket(self, actor: UserAccount, ticket_id: UUID) -> TicketRecord:
        ticket = self.get_visible_ticket(actor, ticket_id)
        # Read-all visibility never confers write access: edits require
        # ownership, editor collaboration, or the explicit write-all grant.
        if (
            not is_owner(actor, ticket)
            and not is_editor(actor, ticket)
            and Permission.TICKET_WRITE_ALL not in actor.permissions
        ):
            raise AppError(404, "ticket_not_found", "Ticket was not found.")
        if ticket.state not in {TicketState.DRAFT_INTAKE, TicketState.INFO_REQUIRED}:
            raise AppError(409, "ticket_not_editable", "Ticket intake is no longer editable.")
        return ticket

    def save_system_update(self, ticket: TicketRecord) -> TicketRecord:
        return self._save(ticket)

    def state_for_intake(self, current: TicketState, intake: IntakeDetails) -> TicketState:
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

    def _save(self, ticket: TicketRecord) -> TicketRecord:
        updated = replace(ticket, updated_at=datetime.now(UTC))
        self._repository.save(updated)
        return updated

    def _can_read(self, actor: UserAccount, ticket: TicketRecord) -> bool:
        return (
            is_owner(actor, ticket)
            or is_collaborator(actor, ticket)
            or Permission.TICKET_READ_ALL in actor.permissions
        )
