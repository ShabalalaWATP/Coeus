"""Customer-safe status, journey and provisional forecast projections."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from coeus.domain.auth import UserAccount
from coeus.domain.enums import TicketState
from coeus.domain.tickets import RoutingRoute, TicketRecord
from coeus.services.analyst_records import active_assignments, approved_route
from coeus.services.customer_status_copy import action_type, remaining_hours, terminal_copy

ACTION_STATES = frozenset(
    {
        TicketState.INFO_REQUIRED,
        TicketState.RFI_SEARCH_INCOMPLETE,
        TicketState.RFI_NO_MATCH,
        TicketState.RFI_MATCH_OFFERED,
        TicketState.ACTIVE_WORK_SEARCH_INCOMPLETE,
        TicketState.ACTIVE_WORK_REVIEW,
        TicketState.NEW_TASKING_CONSENT,
        TicketState.COLLECT_CHOICE,
        TicketState.DISSEMINATION_READY,
    }
)
TERMINAL_STATES = frozenset(
    {
        TicketState.CLOSED_DELIVERED,
        TicketState.CLOSED_EXISTING_PRODUCT_ACCEPTED,
        TicketState.CLOSED_UNANSWERED,
        TicketState.CLOSED_JOINED_EXISTING_WORK,
        TicketState.CANCELLED,
        TicketState.CLOSED_REQUIREMENT_MET,
        TicketState.CLOSED_REANALYSIS_DECLINED,
    }
)
PAUSED_STATES = ACTION_STATES | {TicketState.JIOC_INTERVENTION_HOLD}


@dataclass(frozen=True)
class CustomerEstimate:
    earliest: datetime | None
    likely: datetime | None
    latest: datetime | None
    confidence: str
    status: str
    as_of: datetime
    policy_version: str = "provisional-v1"


@dataclass(frozen=True)
class CustomerJourneyStage:
    code: str
    label: str
    status: str


@dataclass(frozen=True)
class CustomerStatus:
    code: str
    label: str
    explanation: str
    current_leg: str
    action_required: bool
    action_type: str | None
    next_milestone: str | None
    canonical_ticket_id: UUID | None
    estimate: CustomerEstimate | None
    journey: tuple[CustomerJourneyStage, ...]


def customer_status(
    ticket: TicketRecord, actor: UserAccount, *, now: datetime | None = None
) -> CustomerStatus:
    current_time = now or datetime.now(UTC)
    code, label, explanation, leg, next_milestone = _status_copy(ticket)
    is_owner = ticket.requester_user_id == actor.user_id
    action_required = is_owner and ticket.state in ACTION_STATES
    return CustomerStatus(
        code,
        label,
        explanation,
        leg,
        action_required,
        action_type(ticket.state) if action_required else None,
        next_milestone,
        ticket.duplicate_of_ticket_id
        if ticket.state == TicketState.CLOSED_JOINED_EXISTING_WORK
        else None,
        _estimate(ticket, current_time),
        _journey(ticket),
    )


StatusCopy = tuple[str, str, str, str, str | None]


def _status_copy(ticket: TicketRecord) -> StatusCopy:
    state = ticket.state
    for value in (
        _intake_search_copy(state),
        _routing_copy(state),
        _production_copy(ticket),
        _delivery_copy(state),
    ):
        if value is not None:
            return value
    if state in TERMINAL_STATES:
        return terminal_copy(ticket)
    raise ValueError(f"Customer status copy is missing for {state.value}.")


def _intake_search_copy(state: TicketState) -> StatusCopy | None:
    if state in {TicketState.DRAFT_INTAKE, TicketState.INFO_REQUIRED}:
        return (
            "requirement",
            "Requirement being prepared",
            "More detail is needed.",
            "intake",
            "Submit the completed requirement",
        )
    if state == TicketState.RFI_SEARCHING:
        return (
            "searching",
            "Searching existing intelligence",
            "Istari is checking accessible products.",
            "search",
            "Review search results",
        )
    if state in {TicketState.RFI_SEARCH_INCOMPLETE, TicketState.ACTIVE_WORK_SEARCH_INCOMPLETE}:
        return (
            "search_incomplete",
            "Search needs retrying",
            "The authorised search did not complete.",
            "search",
            "Retry the search",
        )
    if state == TicketState.RFI_NO_MATCH:
        return (
            "no_match",
            "No matching intelligence found",
            "Decide whether to start new tasking for this requirement.",
            "search",
            "Approve or decline new tasking",
        )
    if state == TicketState.RFI_MATCH_OFFERED:
        return (
            "products_offered",
            "Possible answers found",
            "Review the products found in the intelligence store.",
            "search",
            "Accept or reject each product",
        )
    if state == TicketState.ACTIVE_WORK_REVIEW:
        return (
            "active_work_offered",
            "Similar work found",
            "Review matching work already in progress.",
            "search",
            "Join or continue separately",
        )
    if state == TicketState.NEW_TASKING_CONSENT:
        return (
            "tasking_consent",
            "Decision needed",
            "No accepted existing answer remains.",
            "search",
            "Approve or decline new tasking",
        )
    return None


def _routing_copy(state: TicketState) -> StatusCopy | None:
    if state in {TicketState.JIOC_ROUTING_PENDING, TicketState.JIOC_REVIEW}:
        return (
            "routing",
            "Routing the request",
            "The request is being routed to the right capability.",
            "routing",
            "Team assignment",
        )
    if state == TicketState.JIOC_INTERVENTION_HOLD:
        return (
            "jioc_hold",
            "Paused by JIOC manager",
            "Work is paused while a routing concern is resolved.",
            "routing",
            "Manager resolution",
        )
    if state == TicketState.COLLECT_CHOICE:
        return (
            "collection_choice",
            "Collection choice needed",
            "Choose raw collection or collection followed by assessment.",
            "collection",
            "Customer collection choice",
        )
    return None


def _production_copy(ticket: TicketRecord) -> StatusCopy | None:
    state = ticket.state
    if state in {TicketState.ANALYST_ASSIGNMENT, TicketState.ANALYST_IN_PROGRESS}:
        leg = _production_leg(ticket)
        label = "Collection underway" if leg == "collection" else "Assessment underway"
        return (
            f"{leg}_in_progress",
            label,
            f"The {leg} team is working on the request.",
            leg,
            "Manager review",
        )
    if state == TicketState.MANAGER_APPROVAL:
        return (
            "manager_review",
            "Team manager review",
            "The draft is undergoing team review.",
            _production_leg(ticket),
            "Quality review",
        )
    if state in {TicketState.QC_REVIEW, TicketState.REWORK_REQUIRED}:
        return (
            "quality_review",
            "Quality review",
            "The product is being checked before release.",
            "quality",
            "Release to customer",
        )
    return None


def _delivery_copy(state: TicketState) -> StatusCopy | None:
    if state == TicketState.DISSEMINATION_READY:
        return (
            "customer_review",
            "Review the released product",
            "Decide whether the released product meets your requirement.",
            "delivery",
            "Accept the answer or explain what is missing",
        )
    if state == TicketState.MANAGER_REANALYSIS_REVIEW:
        return (
            "manager_reanalysis_review",
            "Re-analysis request under review",
            "The responsible team manager is reviewing your reasons.",
            "quality",
            "Manager decision",
        )
    if state == TicketState.JIOC_REANALYSIS_ADJUDICATION:
        return (
            "jioc_reanalysis_review",
            "Re-analysis decision referred to JIOC",
            "An independent JIOC human is making the final decision.",
            "routing",
            "JIOC decision",
        )
    return None


def _production_leg(ticket: TicketRecord) -> str:
    assignments = active_assignments(ticket)
    route = assignments[-1].route if assignments else approved_route(ticket)
    return "collection" if route == RoutingRoute.CM else "assessment"


def _estimate(ticket: TicketRecord, now: datetime) -> CustomerEstimate | None:
    if ticket.state in TERMINAL_STATES:
        return None
    if ticket.state in PAUSED_STATES:
        return CustomerEstimate(None, None, None, "unavailable", "paused", now)
    hours = remaining_hours(ticket.state)
    factor = {"critical": 0.45, "high": 0.7, "medium": 0.9, "routine": 1.0, "low": 1.4}.get(
        (ticket.intake.priority or "routine").casefold(), 1.0
    )
    likely_hours = max(2.0, hours * factor)
    latest = now + timedelta(hours=likely_hours * 1.5)
    deadline = _deadline(ticket)
    status = "at_risk" if deadline is not None and latest > deadline else "provisional"
    return CustomerEstimate(
        now + timedelta(hours=likely_hours * 0.6),
        now + timedelta(hours=likely_hours),
        latest,
        "low",
        status,
        now,
    )


def _deadline(ticket: TicketRecord) -> datetime | None:
    try:
        value = datetime.fromisoformat(ticket.intake.deadline or "")
    except ValueError:
        return None
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


def _journey(ticket: TicketRecord) -> tuple[CustomerJourneyStage, ...]:
    stages = [
        ("intake", "Describe the need"),
        ("search", "Search existing intelligence and work"),
        ("routing", "Route the request"),
    ]
    route = approved_route(ticket)
    if route == RoutingRoute.CM:
        stages.append(("collection", "Collection"))
    if route != RoutingRoute.CM or ticket.collect_disposition == "analysed":
        stages.append(("assessment", "Assessment"))
    stages.extend((("quality", "Quality review"), ("delivery", "Delivery")))
    if ticket.state in TERMINAL_STATES:
        return _terminal_journey(ticket.state, stages)
    current = _status_copy(ticket)[3]
    current_index = next((index for index, item in enumerate(stages) if item[0] == current), 0)
    return tuple(
        CustomerJourneyStage(
            code,
            label,
            "complete"
            if index < current_index
            else "current"
            if index == current_index
            else "upcoming",
        )
        for index, (code, label) in enumerate(stages)
    )


def _terminal_journey(
    state: TicketState, stages: list[tuple[str, str]]
) -> tuple[CustomerJourneyStage, ...]:
    if state in {
        TicketState.CLOSED_DELIVERED,
        TicketState.CLOSED_REQUIREMENT_MET,
        TicketState.CLOSED_REANALYSIS_DECLINED,
    }:
        completed = {code for code, _ in stages}
    elif state == TicketState.CLOSED_EXISTING_PRODUCT_ACCEPTED:
        completed = {"intake", "search", "delivery"}
    elif state in {TicketState.CLOSED_JOINED_EXISTING_WORK, TicketState.CLOSED_UNANSWERED}:
        completed = {"intake", "search"}
    else:
        completed = set()
    return tuple(
        CustomerJourneyStage(code, label, "complete" if code in completed else "not_required")
        for code, label in stages
    )
