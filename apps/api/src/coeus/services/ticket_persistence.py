from dataclasses import replace
from datetime import UTC, datetime

from coeus.core.errors import AppError
from coeus.domain.auth import UserAccount
from coeus.domain.tickets import TicketRecord
from coeus.repositories.tickets import InMemoryTicketRepository
from coeus.services.audit import AuditLog


def save_ticket(repository: InMemoryTicketRepository, ticket: TicketRecord) -> TicketRecord:
    updated = replace(ticket, updated_at=datetime.now(UTC))
    repository.save(updated)
    return updated


def save_audited_ticket(
    repository: InMemoryTicketRepository,
    audit_log: AuditLog,
    ticket: TicketRecord,
    event_type: str,
    actor: UserAccount,
    metadata: dict[str, str],
) -> TicketRecord:
    updated = replace(ticket, updated_at=datetime.now(UTC))
    repository.save_with_confirmation(
        updated,
        lambda: audit_log.record(event_type, str(actor.user_id), metadata),
    )
    return updated


def save_ticket_if_current(
    repository: InMemoryTicketRepository,
    expected: TicketRecord,
    proposed: TicketRecord,
) -> TicketRecord:
    updated = replace(proposed, updated_at=datetime.now(UTC))
    if not repository.save_if_current(expected, updated):
        raise AppError(
            409,
            "ticket_changed",
            "The ticket changed while the operation was running. Retry the operation.",
        )
    return updated
