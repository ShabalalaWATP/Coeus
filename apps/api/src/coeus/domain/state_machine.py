from coeus.domain.enums import TicketState

ALLOWED_TRANSITIONS: dict[TicketState, frozenset[TicketState]] = {
    TicketState.DRAFT_INTAKE: frozenset(
        {TicketState.INFO_REQUIRED, TicketState.RFI_SEARCHING, TicketState.CANCELLED}
    ),
    TicketState.INFO_REQUIRED: frozenset(
        {TicketState.DRAFT_INTAKE, TicketState.JIOC_REVIEW, TicketState.CANCELLED}
    ),
    TicketState.RFI_SEARCHING: frozenset(
        {
            TicketState.RFI_MATCH_OFFERED,
            TicketState.RFI_SEARCH_INCOMPLETE,
            TicketState.ACTIVE_WORK_REVIEW,
            TicketState.NEW_TASKING_CONSENT,
            TicketState.CANCELLED,
        }
    ),
    TicketState.RFI_SEARCH_INCOMPLETE: frozenset(
        {
            TicketState.RFI_MATCH_OFFERED,
            TicketState.NEW_TASKING_CONSENT,
            TicketState.CANCELLED,
        }
    ),
    # Retained for persisted tickets created before the unified consent state.
    TicketState.RFI_NO_MATCH: frozenset(
        {TicketState.JIOC_ROUTING_PENDING, TicketState.CLOSED_UNANSWERED}
    ),
    TicketState.RFI_MATCH_OFFERED: frozenset(
        {
            TicketState.CLOSED_EXISTING_PRODUCT_ACCEPTED,
            TicketState.RFI_SEARCH_INCOMPLETE,
            TicketState.ACTIVE_WORK_REVIEW,
            TicketState.NEW_TASKING_CONSENT,
            TicketState.CANCELLED,
        }
    ),
    TicketState.ACTIVE_WORK_REVIEW: frozenset(
        {
            TicketState.NEW_TASKING_CONSENT,
            TicketState.CLOSED_JOINED_EXISTING_WORK,
            TicketState.CANCELLED,
        }
    ),
    TicketState.ACTIVE_WORK_SEARCH_INCOMPLETE: frozenset(
        {
            TicketState.ACTIVE_WORK_REVIEW,
            TicketState.NEW_TASKING_CONSENT,
            TicketState.CANCELLED,
        }
    ),
    TicketState.NEW_TASKING_CONSENT: frozenset(
        {
            TicketState.ACTIVE_WORK_REVIEW,
            TicketState.ACTIVE_WORK_SEARCH_INCOMPLETE,
            TicketState.JIOC_ROUTING_PENDING,
            TicketState.CLOSED_UNANSWERED,
            TicketState.CANCELLED,
        }
    ),
    TicketState.JIOC_ROUTING_PENDING: frozenset(
        {
            TicketState.INFO_REQUIRED,
            TicketState.JIOC_REVIEW,
            TicketState.ANALYST_ASSIGNMENT,
            TicketState.COLLECT_CHOICE,
            TicketState.CANCELLED,
            TicketState.JIOC_INTERVENTION_HOLD,
        }
    ),
    TicketState.JIOC_REVIEW: frozenset(
        {
            TicketState.INFO_REQUIRED,
            TicketState.ANALYST_ASSIGNMENT,
            TicketState.COLLECT_CHOICE,
            TicketState.CANCELLED,
            TicketState.JIOC_INTERVENTION_HOLD,
        }
    ),
    TicketState.JIOC_INTERVENTION_HOLD: frozenset(
        {
            TicketState.JIOC_ROUTING_PENDING,
            TicketState.JIOC_REVIEW,
            TicketState.COLLECT_CHOICE,
            TicketState.ANALYST_ASSIGNMENT,
            TicketState.ANALYST_IN_PROGRESS,
            TicketState.MANAGER_APPROVAL,
            TicketState.QC_REVIEW,
            TicketState.REWORK_REQUIRED,
            TicketState.CANCELLED,
        }
    ),
    TicketState.COLLECT_CHOICE: frozenset(
        {
            TicketState.ANALYST_ASSIGNMENT,
            TicketState.JIOC_REVIEW,
            TicketState.JIOC_INTERVENTION_HOLD,
            TicketState.CANCELLED,
        }
    ),
    TicketState.ANALYST_ASSIGNMENT: frozenset(
        {
            TicketState.ANALYST_IN_PROGRESS,
            TicketState.JIOC_REVIEW,
            TicketState.JIOC_INTERVENTION_HOLD,
            TicketState.CANCELLED,
        }
    ),
    TicketState.ANALYST_IN_PROGRESS: frozenset(
        {
            TicketState.MANAGER_APPROVAL,
            TicketState.JIOC_INTERVENTION_HOLD,
            TicketState.CANCELLED,
        }
    ),
    TicketState.MANAGER_APPROVAL: frozenset(
        {
            TicketState.ANALYST_IN_PROGRESS,
            TicketState.QC_REVIEW,
            TicketState.JIOC_INTERVENTION_HOLD,
            TicketState.CANCELLED,
        }
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
            TicketState.JIOC_INTERVENTION_HOLD,
        }
    ),
    TicketState.REWORK_REQUIRED: frozenset(
        {
            TicketState.QC_REVIEW,
            TicketState.JIOC_INTERVENTION_HOLD,
            TicketState.CANCELLED,
        }
    ),
    TicketState.DISSEMINATION_READY: frozenset(
        {
            TicketState.CLOSED_DELIVERED,
            TicketState.CLOSED_REQUIREMENT_MET,
            TicketState.MANAGER_REANALYSIS_REVIEW,
        }
    ),
    TicketState.MANAGER_REANALYSIS_REVIEW: frozenset(
        {TicketState.ANALYST_IN_PROGRESS, TicketState.JIOC_REANALYSIS_ADJUDICATION}
    ),
    TicketState.JIOC_REANALYSIS_ADJUDICATION: frozenset(
        {TicketState.ANALYST_IN_PROGRESS, TicketState.CLOSED_REANALYSIS_DECLINED}
    ),
    TicketState.CLOSED_REQUIREMENT_MET: frozenset(),
    TicketState.CLOSED_REANALYSIS_DECLINED: frozenset(),
    TicketState.CLOSED_DELIVERED: frozenset(),
    TicketState.CLOSED_EXISTING_PRODUCT_ACCEPTED: frozenset(),
    TicketState.CLOSED_UNANSWERED: frozenset(),
    TicketState.CLOSED_JOINED_EXISTING_WORK: frozenset(),
    TicketState.CANCELLED: frozenset(),
}


def can_transition(current: TicketState, target: TicketState) -> bool:
    return target in ALLOWED_TRANSITIONS[current]
