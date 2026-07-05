from coeus.domain.enums import TicketState

ALLOWED_TRANSITIONS: dict[TicketState, frozenset[TicketState]] = {
    TicketState.DRAFT_INTAKE: frozenset({TicketState.INFO_REQUIRED, TicketState.RFI_SEARCHING}),
    TicketState.INFO_REQUIRED: frozenset({TicketState.DRAFT_INTAKE, TicketState.ROUTE_ASSESSMENT}),
    TicketState.RFI_SEARCHING: frozenset(
        {TicketState.RFI_MATCH_OFFERED, TicketState.ROUTE_ASSESSMENT}
    ),
    TicketState.RFI_MATCH_OFFERED: frozenset(
        {TicketState.CLOSED_EXISTING_PRODUCT_ACCEPTED, TicketState.ROUTE_ASSESSMENT}
    ),
    TicketState.ROUTE_ASSESSMENT: frozenset(
        {
            TicketState.INFO_REQUIRED,
            TicketState.RFA_MANAGER_REVIEW,
            TicketState.CM_MANAGER_REVIEW,
            TicketState.CANCELLED,
        }
    ),
    TicketState.RFA_MANAGER_REVIEW: frozenset(
        {
            TicketState.INFO_REQUIRED,
            TicketState.CM_MANAGER_REVIEW,
            TicketState.ANALYST_ASSIGNMENT,
            TicketState.CANCELLED,
        }
    ),
    TicketState.CM_MANAGER_REVIEW: frozenset(
        {TicketState.INFO_REQUIRED, TicketState.ANALYST_ASSIGNMENT, TicketState.CANCELLED}
    ),
    TicketState.ANALYST_ASSIGNMENT: frozenset(
        {TicketState.ANALYST_IN_PROGRESS, TicketState.CANCELLED}
    ),
    TicketState.ANALYST_IN_PROGRESS: frozenset({TicketState.QC_REVIEW, TicketState.CANCELLED}),
    TicketState.QC_REVIEW: frozenset(
        {TicketState.REWORK_REQUIRED, TicketState.DISSEMINATION_READY, TicketState.CANCELLED}
    ),
    TicketState.REWORK_REQUIRED: frozenset({TicketState.QC_REVIEW, TicketState.CANCELLED}),
    TicketState.DISSEMINATION_READY: frozenset(),
    TicketState.CLOSED_EXISTING_PRODUCT_ACCEPTED: frozenset(),
    TicketState.CANCELLED: frozenset(),
}


def can_transition(current: TicketState, target: TicketState) -> bool:
    return target in ALLOWED_TRANSITIONS[current]
