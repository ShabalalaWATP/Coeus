"""Customer-safe terminal, action and forecast copy."""

from coeus.domain.enums import TicketState
from coeus.domain.tickets import TicketRecord


def terminal_copy(ticket: TicketRecord) -> tuple[str, str, str, str, None]:
    values = {
        TicketState.CLOSED_DELIVERED: (
            "delivered",
            "Delivered",
            "The product was delivered and confirmed.",
        ),
        TicketState.CLOSED_EXISTING_PRODUCT_ACCEPTED: (
            "answered_existing",
            "Answered from existing intelligence",
            "An existing product was accepted.",
        ),
        TicketState.CLOSED_UNANSWERED: (
            "closed_unanswered",
            "Closed without new tasking",
            "No answer was accepted and new work was declined.",
        ),
        TicketState.CLOSED_JOINED_EXISTING_WORK: (
            "joined_existing",
            "Joined existing work",
            "Progress continues on the linked request.",
        ),
        TicketState.CANCELLED: ("cancelled", "Cancelled", "The request was cancelled."),
        TicketState.CLOSED_REQUIREMENT_MET: (
            "requirement_met",
            "Requirement met",
            "You confirmed that the released product met the requirement.",
        ),
        TicketState.CLOSED_REANALYSIS_DECLINED: (
            "reanalysis_declined",
            "Closed after JIOC review",
            "JIOC decided that further analysis was not required.",
        ),
    }
    code, label, explanation = values.get(
        ticket.state, ("workflow", "In progress", "The request is in progress.")
    )
    return code, label, explanation, "complete", None


def action_type(state: TicketState) -> str:
    return {
        TicketState.INFO_REQUIRED: "provide_information",
        TicketState.RFI_SEARCH_INCOMPLETE: "retry_product_search",
        TicketState.ACTIVE_WORK_SEARCH_INCOMPLETE: "retry_active_work_search",
        TicketState.RFI_NO_MATCH: "decide_new_tasking",
        TicketState.RFI_MATCH_OFFERED: "review_products",
        TicketState.ACTIVE_WORK_REVIEW: "review_active_work",
        TicketState.NEW_TASKING_CONSENT: "decide_new_tasking",
        TicketState.COLLECT_CHOICE: "choose_collection_output",
        TicketState.DISSEMINATION_READY: "decide_product_outcome",
    }[state]


def remaining_hours(state: TicketState) -> float:
    return {
        TicketState.RFI_SEARCHING: 84,
        TicketState.JIOC_ROUTING_PENDING: 80,
        TicketState.JIOC_REVIEW: 80,
        TicketState.ANALYST_ASSIGNMENT: 72,
        TicketState.ANALYST_IN_PROGRESS: 56,
        TicketState.MANAGER_APPROVAL: 24,
        TicketState.QC_REVIEW: 16,
        TicketState.REWORK_REQUIRED: 32,
        TicketState.MANAGER_REANALYSIS_REVIEW: 24,
        TicketState.JIOC_REANALYSIS_ADJUDICATION: 24,
    }.get(state, 48)
