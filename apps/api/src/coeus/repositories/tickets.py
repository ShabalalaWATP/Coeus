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
        existing = {ticket.reference for ticket in self._tickets.values()}
        while True:
            self._counter += 1
            reference = f"TCK-{self._counter:04d}"
            if reference not in existing:
                return reference

    def save(self, ticket: TicketRecord) -> None:
        tickets = dict(self._tickets)
        self._tickets[ticket.ticket_id] = ticket
        try:
            self._persist()
        except Exception:
            self._tickets = tickets
            raise

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
        # Restore from the highest issued reference, not the item count, so
        # deletions can never cause a reference to be handed out twice.
        self._counter = max(
            int(payload.get("counter", 0)),
            _max_reference_counter(tickets),
        )

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


def _max_reference_counter(tickets: tuple[TicketRecord, ...]) -> int:
    counter = 0
    for ticket in tickets:
        prefix, _, suffix = ticket.reference.partition("-")
        if prefix == "TCK" and suffix.isdigit():
            counter = max(counter, int(suffix))
    return counter
