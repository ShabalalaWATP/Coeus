"""Retention policy for ticket-capacity accounting."""

from coeus.domain.enums import TicketState
from coeus.domain.state_machine import ALLOWED_TRANSITIONS

# Terminal states are exactly the states with no permitted onward transition.
# Deriving the set from the state machine keeps capacity accounting aligned
# when new closure states are added.
TERMINAL_TICKET_STATES: frozenset[TicketState] = frozenset(
    state for state, targets in ALLOWED_TRANSITIONS.items() if not targets
)


def terminal_state_names() -> tuple[str, ...]:
    """Sorted terminal state values for SQL projections and backfills."""
    return tuple(sorted(state.value for state in TERMINAL_TICKET_STATES))


def ticket_consumes_capacity(state: TicketState) -> bool:
    """Return whether a ticket occupies retained workflow capacity."""
    return state not in TERMINAL_TICKET_STATES
