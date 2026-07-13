"""Application persistence boundary for ticket aggregates."""

from collections.abc import Callable
from typing import Protocol
from uuid import UUID

from coeus.domain.tickets import TicketRecord


class TicketRepository(Protocol):
    def next_reference(self) -> str: ...

    def save(self, ticket: TicketRecord) -> None: ...

    def save_with_confirmation(self, ticket: TicketRecord, confirm: Callable[[], object]) -> None:
        """Persist only when the compatibility side effect succeeds."""
        ...

    def save_if_current(self, expected: TicketRecord, updated: TicketRecord) -> bool: ...

    def get(self, ticket_id: UUID) -> TicketRecord | None: ...

    def list_tickets(self) -> tuple[TicketRecord, ...]: ...

    def accept_committed(self, ticket: TicketRecord) -> None: ...
