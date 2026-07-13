"""Retention policy for ticket-capacity accounting."""

from coeus.domain.enums import TicketState

TERMINAL_TICKET_STATES = frozenset(
    {
        TicketState.CANCELLED,
        TicketState.CLOSED_DELIVERED,
        TicketState.CLOSED_EXISTING_PRODUCT_ACCEPTED,
    }
)


def ticket_consumes_capacity(state: TicketState) -> bool:
    """Return whether a ticket occupies retained workflow capacity."""
    return state not in TERMINAL_TICKET_STATES
