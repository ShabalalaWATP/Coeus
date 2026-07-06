from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID

from coeus.core.errors import AppError
from coeus.core.permissions import Permission
from coeus.domain.auth import UserAccount
from coeus.domain.tickets import CollaboratorAccess, TicketCollaborator, TicketRecord
from coeus.repositories.auth import SeedUserRepository
from coeus.services.audit import AuditLog
from coeus.services.ticket_records import is_owner, timeline
from coeus.services.tickets import TicketService


class TicketCollaboratorService:
    """Lets requesters tag other users into a ticket as editors or viewers."""

    def __init__(
        self,
        users: SeedUserRepository,
        tickets: TicketService,
        audit_log: AuditLog,
    ) -> None:
        self._users = users
        self._tickets = tickets
        self._audit_log = audit_log

    def directory(self, actor: UserAccount) -> tuple[UserAccount, ...]:
        """Active accounts a signed-in user can tag, excluding themselves."""
        return tuple(
            user
            for user in self._users.list_users()
            if user.is_active and user.user_id != actor.user_id
        )

    def add(
        self,
        actor: UserAccount,
        ticket_id: UUID,
        username: str,
        access: CollaboratorAccess,
    ) -> TicketRecord:
        ticket = self._owned_ticket(actor, ticket_id)
        user = self._users.get_by_username(username)
        if user is None or not user.is_active or user.user_id == ticket.requester_user_id:
            raise AppError(422, "collaborator_invalid", "This user cannot be added to the ticket.")
        collaborator = TicketCollaborator(
            user_id=user.user_id,
            username=user.username,
            display_name=user.display_name,
            access=access,
            added_by_user_id=actor.user_id,
            created_at=datetime.now(UTC),
        )
        others = tuple(
            existing for existing in ticket.collaborators if existing.user_id != user.user_id
        )
        updated = self._tickets.save_system_update(
            replace(
                ticket,
                collaborators=(*others, collaborator),
                timeline=(
                    *ticket.timeline,
                    timeline(
                        ticket.ticket_id,
                        actor.user_id,
                        "collaborator_added",
                        f"{user.display_name} tagged as {access.value}.",
                    ),
                ),
            )
        )
        self._audit_log.record(
            "ticket_collaborator_added",
            str(actor.user_id),
            {
                "ticket_id": str(ticket.ticket_id),
                "collaborator_user_id": str(user.user_id),
                "access": access.value,
            },
        )
        return updated

    def remove(self, actor: UserAccount, ticket_id: UUID, user_id: UUID) -> TicketRecord:
        ticket = self._owned_ticket(actor, ticket_id)
        removed = next(
            (existing for existing in ticket.collaborators if existing.user_id == user_id),
            None,
        )
        if removed is None:
            raise AppError(404, "collaborator_not_found", "Collaborator was not found.")
        updated = self._tickets.save_system_update(
            replace(
                ticket,
                collaborators=tuple(
                    existing for existing in ticket.collaborators if existing.user_id != user_id
                ),
                timeline=(
                    *ticket.timeline,
                    timeline(
                        ticket.ticket_id,
                        actor.user_id,
                        "collaborator_removed",
                        f"{removed.display_name} untagged.",
                    ),
                ),
            )
        )
        self._audit_log.record(
            "ticket_collaborator_removed",
            str(actor.user_id),
            {"ticket_id": str(ticket.ticket_id), "collaborator_user_id": str(user_id)},
        )
        return updated

    def _owned_ticket(self, actor: UserAccount, ticket_id: UUID) -> TicketRecord:
        ticket = self._tickets.get_visible_ticket(actor, ticket_id)
        if not is_owner(actor, ticket) and Permission.TICKET_READ_ALL not in actor.permissions:
            raise AppError(404, "ticket_not_found", "Ticket was not found.")
        return ticket
