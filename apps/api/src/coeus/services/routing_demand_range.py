"""Bounded demand evidence for relational JIOC shadow evaluation."""

from dataclasses import dataclass
from enum import StrEnum

DEMAND_RANGE_VERSION = "jioc-routing-demand-range-v1"
MAX_DEMAND_MINUTES = 31 * 24 * 60
RELATIONAL_DELIVERY_LEAVES = frozenset(
    {
        "rfa_maritime",
        "rfa_land",
        "rfa_cyber",
        "rfa_regional",
        "cm_open",
        "cm_geo",
        "cm_requirements",
    }
)


class DemandCapacityComparison(StrEnum):
    UNKNOWN = "unknown"
    BELOW = "below"
    INSIDE = "inside"
    MEETS_UPPER_BOUND = "meets_upper_bound"


@dataclass(frozen=True)
class RoutingDemandRange:
    """Approved aggregate effort bounds for one candidate delivery interval."""

    leaf_key: str
    lower_minutes: int
    upper_minutes: int
    version: str = DEMAND_RANGE_VERSION

    def __post_init__(self) -> None:
        if self.leaf_key not in RELATIONAL_DELIVERY_LEAVES:
            raise ValueError("routing demand leaf is not a relational delivery leaf")
        if not self.version or len(self.version) > 80:
            raise ValueError("routing demand version is invalid")
        if (
            self.lower_minutes <= 0
            or self.lower_minutes % 15
            or self.upper_minutes < self.lower_minutes
            or self.upper_minutes % 15
            or self.upper_minutes > MAX_DEMAND_MINUTES
        ):
            raise ValueError("routing demand range is invalid")


def compare_capacity_to_demand(
    capacity_minutes: int | None,
    demand: RoutingDemandRange | None,
) -> DemandCapacityComparison:
    """Fail closed unless conserved capacity covers the approved upper bound."""

    if demand is None or capacity_minutes is None:
        return DemandCapacityComparison.UNKNOWN
    if capacity_minutes < 0 or capacity_minutes % 15:
        return DemandCapacityComparison.UNKNOWN
    if capacity_minutes < demand.lower_minutes:
        return DemandCapacityComparison.BELOW
    if capacity_minutes < demand.upper_minutes:
        return DemandCapacityComparison.INSIDE
    return DemandCapacityComparison.MEETS_UPPER_BOUND


def routing_capacity_status(
    capacity_minutes: int | None,
    demand: RoutingDemandRange | None,
) -> str:
    comparison = compare_capacity_to_demand(capacity_minutes, demand)
    if comparison is DemandCapacityComparison.UNKNOWN:
        return "unknown"
    if comparison is DemandCapacityComparison.MEETS_UPPER_BOUND:
        return "available"
    return "unavailable"
