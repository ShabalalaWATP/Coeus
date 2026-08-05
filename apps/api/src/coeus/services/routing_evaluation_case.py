"""Input contract for one labelled JIOC routing evaluation case."""

from dataclasses import dataclass


@dataclass(frozen=True)
class RoutingEvaluationCase:
    case_id: str
    description: str
    output_format: str
    expected_class: str
    expected_disposition: str
    expected_rationale: str
    delivery_leaf: str = "rfa_maritime"
    demand_lower_minutes: int | None = 240
    demand_upper_minutes: int | None = 480
    capacity_minutes: int | None = 480
    search_ready: bool = True
    snapshot_age_seconds: int = 0
    snapshot_present: bool = True
    priority: str = "routine"
    deadline: str | None = "2026-07-21"
    restrictions: str | None = None
    product_offer_unresolved: bool = False
    active_work_completed: bool = True
    active_work_offer_unresolved: bool = False
