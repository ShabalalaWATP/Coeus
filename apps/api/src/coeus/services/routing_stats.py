from dataclasses import dataclass


@dataclass(frozen=True)
class RoutingStats:
    route_assessment_count: int
    rfa_review_count: int
    cm_review_count: int
    clarification_count: int
    analyst_assignment_count: int
    rfa_acceptance_rate: float
    cm_fallback_rate: float
