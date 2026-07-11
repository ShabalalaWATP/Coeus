from coeus.domain.enums import TicketState

ALLOWED_TRANSITIONS: dict[TicketState, frozenset[TicketState]] = {
    TicketState.DRAFT_INTAKE: frozenset(
        {TicketState.INFO_REQUIRED, TicketState.RFI_SEARCHING, TicketState.CANCELLED}
    ),
    TicketState.INFO_REQUIRED: frozenset(
        {TicketState.DRAFT_INTAKE, TicketState.JIOC_REVIEW, TicketState.CANCELLED}
    ),
    TicketState.RFI_SEARCHING: frozenset(
        {TicketState.RFI_MATCH_OFFERED, TicketState.RFI_NO_MATCH, TicketState.CANCELLED}
    ),
    TicketState.RFI_NO_MATCH: frozenset({TicketState.JIOC_REVIEW, TicketState.CANCELLED}),
    TicketState.RFI_MATCH_OFFERED: frozenset(
        {
            TicketState.CLOSED_EXISTING_PRODUCT_ACCEPTED,
            TicketState.JIOC_REVIEW,
            TicketState.CANCELLED,
        }
    ),
    TicketState.JIOC_REVIEW: frozenset(
        {
            TicketState.INFO_REQUIRED,
            TicketState.ANALYST_ASSIGNMENT,
            TicketState.COLLECT_CHOICE,
            TicketState.CANCELLED,
        }
    ),
    TicketState.COLLECT_CHOICE: frozenset({TicketState.ANALYST_ASSIGNMENT, TicketState.CANCELLED}),
    TicketState.ANALYST_ASSIGNMENT: frozenset(
        {TicketState.ANALYST_IN_PROGRESS, TicketState.CANCELLED}
    ),
    TicketState.ANALYST_IN_PROGRESS: frozenset(
        {TicketState.MANAGER_APPROVAL, TicketState.CANCELLED}
    ),
    TicketState.MANAGER_APPROVAL: frozenset(
        {TicketState.ANALYST_IN_PROGRESS, TicketState.QC_REVIEW, TicketState.CANCELLED}
    ),
    # QC approval either releases to the customer (DISSEMINATION_READY) or, for
    # a collect the customer wants analysed, forwards the ticket to RFA
    # assignment for the follow-up analysis leg.
    TicketState.QC_REVIEW: frozenset(
        {
            TicketState.REWORK_REQUIRED,
            TicketState.DISSEMINATION_READY,
            TicketState.ANALYST_ASSIGNMENT,
            TicketState.CANCELLED,
        }
    ),
    TicketState.REWORK_REQUIRED: frozenset({TicketState.QC_REVIEW, TicketState.CANCELLED}),
    TicketState.DISSEMINATION_READY: frozenset({TicketState.CLOSED_DELIVERED}),
    TicketState.CLOSED_DELIVERED: frozenset(),
    TicketState.CLOSED_EXISTING_PRODUCT_ACCEPTED: frozenset(),
    TicketState.CANCELLED: frozenset(),
}


def can_transition(current: TicketState, target: TicketState) -> bool:
    return target in ALLOWED_TRANSITIONS[current]
