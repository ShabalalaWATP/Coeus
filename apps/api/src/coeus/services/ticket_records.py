from datetime import UTC, datetime
from uuid import UUID, uuid4

from coeus.domain.auth import UserAccount
from coeus.domain.tickets import ChatMessage, MessageAuthor, TicketRecord, TicketTimelineEntry


def message(ticket_id: UUID, author: MessageAuthor, body: str) -> ChatMessage:
    return ChatMessage(
        message_id=uuid4(),
        ticket_id=ticket_id,
        author=author,
        body=body,
        created_at=datetime.now(UTC),
    )


def timeline(
    ticket_id: UUID,
    actor_user_id: UUID,
    event_type: str,
    body: str,
) -> TicketTimelineEntry:
    return TicketTimelineEntry(
        entry_id=uuid4(),
        ticket_id=ticket_id,
        event_type=event_type,
        body=body,
        actor_user_id=actor_user_id,
        created_at=datetime.now(UTC),
    )


def suggest_project_name(ticket: TicketRecord) -> str:
    return f"{ticket.intake.title or 'Draft Requirement'} Workspace"


def is_owner(actor: UserAccount, ticket: TicketRecord) -> bool:
    return ticket.requester_user_id == actor.user_id
