from coeus.domain.enums import TicketState

ALLOWED_TRANSITIONS: dict[TicketState, frozenset[TicketState]] = {
    TicketState.DRAFT_INTAKE: frozenset({TicketState.INFO_REQUIRED, TicketState.RFI_SEARCHING}),
    TicketState.INFO_REQUIRED: frozenset({TicketState.DRAFT_INTAKE}),
    TicketState.RFI_SEARCHING: frozenset(
        {TicketState.RFI_MATCH_OFFERED, TicketState.ROUTE_ASSESSMENT}
    ),
    TicketState.RFI_MATCH_OFFERED: frozenset(
        {TicketState.CLOSED_EXISTING_PRODUCT_ACCEPTED, TicketState.ROUTE_ASSESSMENT}
    ),
    TicketState.ROUTE_ASSESSMENT: frozenset({TicketState.CANCELLED}),
    TicketState.CLOSED_EXISTING_PRODUCT_ACCEPTED: frozenset(),
    TicketState.CANCELLED: frozenset(),
}


def can_transition(current: TicketState, target: TicketState) -> bool:
    return target in ALLOWED_TRANSITIONS[current]
