from collections.abc import Callable
from threading import RLock
from typing import Any, Protocol, cast
from uuid import UUID

from coeus.domain.tickets import TicketRecord
from coeus.persistence.codec import decode_value, encode_value
from coeus.persistence.state_store import StateStore


class RelationalTicketStateStore(Protocol):
    ticket_mode: str

    def load_ticket_state(self) -> dict[str, Any]: ...

    def save_ticket_record(self, ticket: dict[str, Any], counter: int) -> None: ...

    def replace_ticket_state(self, payload: dict[str, Any]) -> None: ...

    def compare_and_swap_ticket_record(
        self, expected: dict[str, Any], proposed: dict[str, Any], counter: int
    ) -> bool: ...


class InMemoryTicketRepository:
    def __init__(self, state_store: StateStore | None = None) -> None:
        self._state_store = state_store
        self._relational_store = _relational_ticket_store(state_store)
        self._tickets: dict[UUID, TicketRecord] = {}
        self._counter = 0
        self._lock = RLock()
        self._restore_or_persist()

    def next_reference(self) -> str:
        with self._lock:
            existing = {ticket.reference for ticket in self._tickets.values()}
            while True:
                self._counter += 1
                reference = f"TCK-{self._counter:04d}"
                if reference not in existing:
                    return reference

    def save(self, ticket: TicketRecord) -> None:
        with self._lock:
            self._save_locked(ticket)

    def save_with_confirmation(self, ticket: TicketRecord, confirm: Callable[[], object]) -> None:
        """Persist a ticket only when its required side effect also succeeds."""
        with self._lock:
            tickets = dict(self._tickets)
            self._save_locked(ticket)
            try:
                confirm()
            except Exception:
                self._tickets = tickets
                self._persist()
                raise

    def save_pair_with_confirmation(
        self,
        expected: tuple[TicketRecord, TicketRecord],
        updated: tuple[TicketRecord, TicketRecord],
        confirm: Callable[[], object],
    ) -> bool:
        """Replace two aggregates under one lock, with rollback on confirmation failure."""
        expected_by_id = {ticket.ticket_id: ticket for ticket in expected}
        updated_by_id = {ticket.ticket_id: ticket for ticket in updated}
        if len(expected_by_id) != 2 or set(updated_by_id) != set(expected_by_id):
            raise ValueError("Paired ticket identities must be distinct and unchanged.")
        with self._lock:
            stale = any(
                self._tickets.get(ticket_id) != ticket
                for ticket_id, ticket in expected_by_id.items()
            )
            if stale:
                return False
            tickets = dict(self._tickets)
            self._tickets.update(updated_by_id)
            try:
                self._persist()
                confirm()
            except Exception:
                self._tickets = tickets
                self._persist()
                raise
            return True

    def save_if_current(self, expected: TicketRecord, updated: TicketRecord) -> bool:
        """Atomically replace the expected immutable snapshot, or report a conflict."""
        with self._lock:
            if self._tickets.get(expected.ticket_id) != expected:
                return False
            if self._relational_store is not None:
                saved = self._relational_store.compare_and_swap_ticket_record(
                    encode_value(expected), encode_value(updated), self._counter
                )
                if not saved:
                    self._restore_or_persist()
                    return False
                self._tickets[updated.ticket_id] = updated
                return True
            self._save_locked(updated)
            return True

    def get(self, ticket_id: UUID) -> TicketRecord | None:
        with self._lock:
            return self._tickets.get(ticket_id)

    def list_tickets(self) -> tuple[TicketRecord, ...]:
        with self._lock:
            return tuple(self._tickets.values())

    def accept_committed(self, ticket: TicketRecord) -> None:
        """Update the cache after a transaction port has durably committed."""
        with self._lock:
            self._tickets[ticket.ticket_id] = ticket

    def _save_locked(self, ticket: TicketRecord) -> None:
        tickets = dict(self._tickets)
        self._counter = max(self._counter, _reference_counter(ticket.reference))
        self._tickets[ticket.ticket_id] = ticket
        try:
            self._persist(ticket)
        except Exception:
            self._tickets = tickets
            raise

    def _restore_or_persist(self) -> None:
        if self._state_store is None:
            return
        payload = (
            self._relational_store.load_ticket_state()
            if self._relational_store is not None
            else self._state_store.load("tickets")
        )
        if payload is None:
            self._persist()
            return
        tickets = tuple(decode_value(item) for item in payload.get("tickets", []))
        self._tickets = {ticket.ticket_id: ticket for ticket in tickets}
        # Restore from the highest issued reference, not the item count, so
        # deletions can never cause a reference to be handed out twice.
        self._counter = max(
            int(payload.get("counter", 0)),
            _max_reference_counter(tickets),
        )

    def _persist(self, changed: TicketRecord | None = None) -> None:
        if self._state_store is None:
            return
        tickets = sorted(self._tickets.values(), key=lambda ticket: ticket.created_at)
        payload = {
            "counter": self._counter,
            "tickets": [encode_value(ticket) for ticket in tickets],
        }
        if self._relational_store is not None:
            if changed is None:
                self._relational_store.replace_ticket_state(payload)
            else:
                self._relational_store.save_ticket_record(encode_value(changed), self._counter)
            return
        self._state_store.save("tickets", payload)


def _relational_ticket_store(
    state_store: StateStore | None,
) -> RelationalTicketStateStore | None:
    if state_store is None or getattr(state_store, "ticket_mode", None) != "relational":
        return None
    return cast(RelationalTicketStateStore, state_store)


def _max_reference_counter(tickets: tuple[TicketRecord, ...]) -> int:
    counter = 0
    for ticket in tickets:
        counter = max(counter, _reference_counter(ticket.reference))
    return counter


def _reference_counter(reference: str) -> int:
    prefix, _, suffix = reference.partition("-")
    return int(suffix) if prefix == "TCK" and suffix.isdigit() else 0
