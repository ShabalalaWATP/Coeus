from dataclasses import replace
from datetime import UTC, datetime

from coeus.application.ports.tickets import TicketRepository
from coeus.core.errors import AppError
from coeus.domain.tickets import TicketRecord


def save_ticket(repository: TicketRepository, ticket: TicketRecord) -> TicketRecord:
    updated = replace(ticket, updated_at=datetime.now(UTC))
    repository.save(updated)
    return updated


def save_ticket_if_current(
    repository: TicketRepository,
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
