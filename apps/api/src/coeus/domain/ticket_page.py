"""Persistence-neutral ticket pagination result."""

from dataclasses import dataclass
from uuid import UUID

from coeus.domain.tickets import TicketRecord


@dataclass(frozen=True)
class TicketPage:
    tickets: tuple[TicketRecord, ...]
    next_cursor: UUID | None
