"""Terminal-state capacity accounting must track the state machine."""

from coeus.domain.enums import TicketState
from coeus.domain.state_machine import ALLOWED_TRANSITIONS
from coeus.domain.ticket_retention import (
    TERMINAL_TICKET_STATES,
    terminal_state_names,
    ticket_consumes_capacity,
)


def test_terminal_states_are_exactly_the_states_with_no_onward_transition() -> None:
    expected = {state for state, targets in ALLOWED_TRANSITIONS.items() if not targets}
    assert expected == TERMINAL_TICKET_STATES
    assert TicketState.CLOSED_REQUIREMENT_MET in TERMINAL_TICKET_STATES
    assert TicketState.CLOSED_REANALYSIS_DECLINED in TERMINAL_TICKET_STATES
    assert TicketState.CLOSED_UNANSWERED in TERMINAL_TICKET_STATES
    assert TicketState.CLOSED_JOINED_EXISTING_WORK in TERMINAL_TICKET_STATES


def test_only_non_terminal_states_consume_capacity() -> None:
    for state in TicketState:
        assert ticket_consumes_capacity(state) is (state not in TERMINAL_TICKET_STATES)


def test_terminal_state_names_cover_every_closure_added_after_the_projection() -> None:
    names = terminal_state_names()
    assert names == tuple(sorted(state.value for state in TERMINAL_TICKET_STATES))
    for late_closure in (
        "CLOSED_JOINED_EXISTING_WORK",
        "CLOSED_REANALYSIS_DECLINED",
        "CLOSED_REQUIREMENT_MET",
        "CLOSED_UNANSWERED",
    ):
        assert late_closure in names
