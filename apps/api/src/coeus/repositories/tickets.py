from uuid import UUID

from coeus.domain.tickets import TicketRecord


class InMemoryTicketRepository:
    def __init__(self) -> None:
        self._tickets: dict[UUID, TicketRecord] = {}
        self._counter = 0

    def next_reference(self) -> str:
        self._counter += 1
        return f"TCK-{self._counter:04d}"

    def save(self, ticket: TicketRecord) -> None:
        self._tickets[ticket.ticket_id] = ticket

    def get(self, ticket_id: UUID) -> TicketRecord | None:
        return self._tickets.get(ticket_id)

    def list_tickets(self) -> tuple[TicketRecord, ...]:
        return tuple(self._tickets.values())

    def list_for_requester(self, requester_user_id: UUID) -> tuple[TicketRecord, ...]:
        return tuple(
            ticket
            for ticket in self._tickets.values()
            if ticket.requester_user_id == requester_user_id
        )
