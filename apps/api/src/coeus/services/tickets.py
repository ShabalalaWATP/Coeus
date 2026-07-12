from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from coeus.core.errors import AppError
from coeus.core.permissions import Permission
from coeus.core.resource_limits import (
    MAX_ATTACHMENT_METADATA_BYTES,
    MAX_TICKET_ATTACHMENTS,
    text_bytes,
)
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
from coeus.services.intake import RequirementCompletenessService, merge_intake
from coeus.services.prioritisation import (
    assessment_or_computed,
    prioritisation_agent_run,
    with_assessment,
)
from coeus.services.ticket_persistence import (
    save_audited_ticket,
    save_ticket,
    save_ticket_if_current,
)
from coeus.services.ticket_records import can_read, is_collaborator, is_editor, is_owner, timeline

if TYPE_CHECKING:
    from coeus.services.ticket_conversations import ConversationService


@dataclass(frozen=True)
class TicketServices:
    tickets: "TicketService"
    conversations: "ConversationService"


@dataclass(frozen=True)
class TicketPage:
    tickets: tuple[TicketRecord, ...]
    next_cursor: UUID | None


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

    def list_visible_ticket_page(
        self, actor: UserAccount, *, cursor: UUID | None, page_size: int
    ) -> TicketPage:
        visible = sorted(
            self.list_visible_tickets(actor),
            key=lambda ticket: (ticket.created_at, ticket.ticket_id),
            reverse=True,
        )
        start = 0
        if cursor is not None:
            try:
                start = next(
                    index + 1 for index, ticket in enumerate(visible) if ticket.ticket_id == cursor
                )
            except StopIteration as exc:
                raise AppError(
                    400, "invalid_ticket_cursor", "The ticket cursor is invalid."
                ) from exc
        selected = tuple(visible[start : start + page_size])
        next_cursor = (
            selected[-1].ticket_id if selected and start + len(selected) < len(visible) else None
        )
        return TicketPage(selected, next_cursor)

    def get_visible_ticket(self, actor: UserAccount, ticket_id: UUID) -> TicketRecord:
        ticket = self._repository.get(ticket_id)
        if ticket is None or not can_read(actor, ticket):
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

    def assignment_snapshot(self) -> tuple[TicketRecord, ...]:
        """System read for availability counts; expose derived numbers only."""
        return self._repository.list_tickets()

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
        self, actor: UserAccount, ticket_id: UUID, updates: dict[str, str | None]
    ) -> TicketRecord:
        ticket = self.get_editable_ticket(actor, ticket_id)
        intake = self._completeness.with_completeness(merge_intake(ticket.intake, updates))
        resumed_routing = (
            ticket.state == TicketState.INFO_REQUIRED
            and bool(ticket.route_recommendations)
            and self._completeness.is_complete_enough(intake)
        )
        entry = timeline(ticket.ticket_id, actor.user_id, "intake_updated", "Intake updated.")
        updated = self._save_audited(
            with_assessment(
                replace(
                    ticket,
                    intake=intake,
                    state=(
                        TicketState.JIOC_REVIEW
                        if resumed_routing
                        else self.state_for_intake(ticket.state, intake)
                    ),
                    timeline=(*ticket.timeline, entry),
                )
            ),
            "ticket_intake_updated",
            actor,
            {"ticket_id": str(ticket.ticket_id)},
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
        projected_bytes = sum(
            text_bytes(item.name, item.description, item.source_type) for item in ticket.attachments
        ) + text_bytes(name, description, source_type)
        if (
            len(ticket.attachments) >= MAX_TICKET_ATTACHMENTS
            or projected_bytes > MAX_ATTACHMENT_METADATA_BYTES
        ):
            raise AppError(
                409,
                "attachment_limit_reached",
                "The ticket has reached its attachment metadata limit.",
            )
        attachment = AttachmentMetadata(
            attachment_id=uuid4(),
            ticket_id=ticket.ticket_id,
            name=name,
            description=description,
            source_type=source_type,
            created_at=datetime.now(UTC),
        )
        return self._save_audited(
            replace(
                ticket,
                attachments=(*ticket.attachments, attachment),
                timeline=(
                    *ticket.timeline,
                    timeline(ticket.ticket_id, actor.user_id, "attachment_added", name),
                ),
            ),
            "ticket_attachment_added",
            actor,
            {"ticket_id": str(ticket.ticket_id), "attachment_id": str(attachment.attachment_id)},
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
        ticket = with_assessment(ticket)
        assessment = assessment_or_computed(ticket)
        priority_run = prioritisation_agent_run(ticket, assessment)
        updated = self._save_audited(
            replace(
                ticket,
                state=TicketState.RFI_SEARCHING,
                agent_runs=(*ticket.agent_runs, priority_run, search_run),
                timeline=(
                    *ticket.timeline,
                    timeline(
                        ticket.ticket_id,
                        actor.user_id,
                        "priority_assessed",
                        f"Internal priority {assessment.tier} recorded.",
                    ),
                    timeline(
                        ticket.ticket_id, actor.user_id, "ticket_submitted", "Ticket submitted."
                    ),
                    timeline(ticket.ticket_id, actor.user_id, "search_started", "Search queued."),
                ),
            ),
            "ticket_submitted",
            actor,
            {"ticket_id": str(ticket.ticket_id)},
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
            TicketState.JIOC_REVIEW
            if ticket.state == TicketState.INFO_REQUIRED and ticket.route_recommendations
            else ticket.state
        )
        entries = (
            *ticket.timeline,
            timeline(ticket.ticket_id, actor.user_id, "information_added", body),
        )
        if state == TicketState.JIOC_REVIEW:
            entries = (
                *entries,
                timeline(
                    ticket.ticket_id,
                    actor.user_id,
                    "route_assessment_resumed",
                    "Requester clarification received.",
                ),
            )
        return self._save_audited(
            replace(
                ticket,
                state=state,
                timeline=entries,
            ),
            "ticket_information_added",
            actor,
            {
                "ticket_id": str(ticket.ticket_id),
                "route_resumed": str(state == TicketState.JIOC_REVIEW).lower(),
            },
        )

    def get_editable_ticket(self, actor: UserAccount, ticket_id: UUID) -> TicketRecord:
        ticket = self.get_visible_ticket(actor, ticket_id)
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
        return save_ticket(self._repository, ticket)

    def save_audited_system_update(
        self,
        ticket: TicketRecord,
        event_type: str,
        actor: UserAccount,
        metadata: dict[str, str],
    ) -> TicketRecord:
        return save_audited_ticket(
            self._repository, self._audit_log, ticket, event_type, actor, metadata
        )

    def save_system_update_if_current(
        self, expected: TicketRecord, proposed: TicketRecord
    ) -> TicketRecord:
        return save_ticket_if_current(self._repository, expected, proposed)

    def restore_system_update_if_current(
        self, expected: TicketRecord, original: TicketRecord
    ) -> bool:
        return self._repository.save_if_current(expected, original)

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
        return save_ticket(self._repository, ticket)

    def _save_audited(
        self,
        ticket: TicketRecord,
        event_type: str,
        actor: UserAccount,
        metadata: dict[str, str],
    ) -> TicketRecord:
        return save_audited_ticket(
            self._repository, self._audit_log, ticket, event_type, actor, metadata
        )
