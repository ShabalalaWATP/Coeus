from datetime import UTC, datetime
from uuid import UUID, uuid4

from coeus.core.permissions import Permission
from coeus.domain.auth import UserAccount
from coeus.domain.tickets import (
    ChatMessage,
    CollaboratorAccess,
    MessageAuthor,
    TicketRecord,
    TicketTimelineEntry,
)


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


def is_owner(actor: UserAccount, ticket: TicketRecord) -> bool:
    return ticket.requester_user_id == actor.user_id


def is_collaborator(actor: UserAccount, ticket: TicketRecord) -> bool:
    return any(collaborator.user_id == actor.user_id for collaborator in ticket.collaborators)


def is_editor(actor: UserAccount, ticket: TicketRecord) -> bool:
    return any(
        collaborator.user_id == actor.user_id and collaborator.access == CollaboratorAccess.EDITOR
        for collaborator in ticket.collaborators
    )


def can_read(actor: UserAccount, ticket: TicketRecord) -> bool:
    return (
        is_owner(actor, ticket)
        or is_collaborator(actor, ticket)
        or Permission.TICKET_READ_ALL in actor.permissions
    )
