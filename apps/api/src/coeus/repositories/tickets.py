from uuid import UUID

from coeus.domain.tickets import TicketRecord
from coeus.persistence.codec import decode_value, encode_value
from coeus.persistence.state_store import StateStore


class InMemoryTicketRepository:
    def __init__(self, state_store: StateStore | None = None) -> None:
        self._state_store = state_store
        self._tickets: dict[UUID, TicketRecord] = {}
        self._counter = 0
        self._restore_or_persist()

    def next_reference(self) -> str:
        self._counter += 1
        return f"TCK-{self._counter:04d}"

    def save(self, ticket: TicketRecord) -> None:
        self._tickets[ticket.ticket_id] = ticket
        self._persist()

    def get(self, ticket_id: UUID) -> TicketRecord | None:
        return self._tickets.get(ticket_id)

    def list_tickets(self) -> tuple[TicketRecord, ...]:
        return tuple(self._tickets.values())

    def _restore_or_persist(self) -> None:
        if self._state_store is None:
            return
        payload = self._state_store.load("tickets")
        if payload is None:
            self._persist()
            return
        tickets = tuple(decode_value(item) for item in payload.get("tickets", []))
        self._tickets = {ticket.ticket_id: ticket for ticket in tickets}
        self._counter = int(payload.get("counter", len(tickets)))

    def _persist(self) -> None:
        if self._state_store is None:
            return
        tickets = sorted(self._tickets.values(), key=lambda ticket: ticket.created_at)
        self._state_store.save(
            "tickets",
            {
                "counter": self._counter,
                "tickets": [encode_value(ticket) for ticket in tickets],
            },
        )
