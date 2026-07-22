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

    def save_with_guarded_confirmation(
        self,
        ticket: TicketRecord,
        guard: Callable[[], object],
        confirm: Callable[[], object],
    ) -> None:
        """Check external state and create under the state-to-ticket lock order."""
        ...

    def save_pair_with_confirmation(
        self,
        expected: tuple[TicketRecord, TicketRecord],
        updated: tuple[TicketRecord, TicketRecord],
        confirm: Callable[[], object],
    ) -> bool:
        """Atomically replace two expected snapshots and run their required confirmation."""
        ...

    def save_if_current(self, expected: TicketRecord, updated: TicketRecord) -> bool: ...

    def save_if_current_with_confirmation(
        self,
        expected: TicketRecord,
        updated: TicketRecord,
        confirm: Callable[[], object],
    ) -> bool:
        """Replace one expected snapshot and roll back if confirmation fails."""
        ...

    def save_if_current_with_guarded_confirmation(
        self,
        expected: TicketRecord,
        updated: TicketRecord,
        guard: Callable[[], object],
        confirm: Callable[[], object],
    ) -> bool:
        """Check external state and persist using the state-to-ticket lock order."""
        ...

    def get(self, ticket_id: UUID) -> TicketRecord | None: ...

    def list_tickets(self) -> tuple[TicketRecord, ...]: ...

    def accept_committed(self, ticket: TicketRecord) -> None: ...
