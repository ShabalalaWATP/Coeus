"""Deterministic assurance and workflow policy for product discovery."""

from dataclasses import dataclass

from coeus.core.permissions import Permission
from coeus.domain.enums import TicketState
from coeus.domain.search_index import GroundedSearchResult
from coeus.domain.search_metrics import RfiSearchMetrics

RFI_RESULTS_REVIEW_PERMISSIONS = frozenset({Permission.RFA_REVIEW, Permission.COLLECTION_REVIEW})
RFI_RESULTS_REVIEW_STATES = frozenset(
    {
        TicketState.RFI_NO_MATCH,
        TicketState.RFI_SEARCH_INCOMPLETE,
        TicketState.NEW_TASKING_CONSENT,
        TicketState.JIOC_ROUTING_PENDING,
        TicketState.JIOC_REVIEW,
        TicketState.COLLECT_CHOICE,
    }
)


@dataclass(frozen=True)
class SearchOutcomeDecision:
    state: TicketState
    outcome: str
    assurance: str


def decide_search_outcome(
    offer_count: int, grounded: GroundedSearchResult
) -> SearchOutcomeDecision:
    if offer_count:
        return SearchOutcomeDecision(TicketState.RFI_MATCH_OFFERED, "offers", "assisted")
    if grounded.coverage_status == "complete" and grounded.degraded_reason is None:
        return SearchOutcomeDecision(
            TicketState.NEW_TASKING_CONSENT,
            "no_match",
            "definitive",
        )
    return SearchOutcomeDecision(
        TicketState.RFI_SEARCH_INCOMPLETE,
        "incomplete",
        "assisted",
    )


def state_after_all_offers_rejected(metrics: RfiSearchMetrics) -> TicketState:
    complete = metrics.coverage_status in {"complete", "legacy"}
    if complete and metrics.degraded_reason is None:
        return TicketState.NEW_TASKING_CONSENT
    return TicketState.RFI_SEARCH_INCOMPLETE
