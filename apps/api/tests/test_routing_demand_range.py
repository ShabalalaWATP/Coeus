import pytest

from coeus.services.routing_demand_range import (
    DemandCapacityComparison,
    RoutingDemandRange,
    compare_capacity_to_demand,
    routing_capacity_status,
)


def test_capacity_must_cover_approved_upper_demand_bound() -> None:
    demand = RoutingDemandRange("rfa_maritime", 240, 480)

    assert compare_capacity_to_demand(225, demand) is DemandCapacityComparison.BELOW
    assert compare_capacity_to_demand(360, demand) is DemandCapacityComparison.INSIDE
    assert compare_capacity_to_demand(480, demand) is DemandCapacityComparison.MEETS_UPPER_BOUND
    assert compare_capacity_to_demand(600, demand) is DemandCapacityComparison.MEETS_UPPER_BOUND
    assert routing_capacity_status(360, demand) == "unavailable"
    assert routing_capacity_status(480, demand) == "available"


def test_missing_or_invalid_capacity_and_demand_fail_closed() -> None:
    demand = RoutingDemandRange("cm_geo", 240, 480)

    assert compare_capacity_to_demand(None, demand) is DemandCapacityComparison.UNKNOWN
    assert compare_capacity_to_demand(481, demand) is DemandCapacityComparison.UNKNOWN
    assert routing_capacity_status(480, None) == "unknown"


@pytest.mark.parametrize(
    ("leaf", "lower", "upper"),
    (("not-a-leaf", 240, 480), ("cm_open", 0, 480), ("cm_open", 480, 240)),
)
def test_demand_range_rejects_unbounded_or_unknown_evidence(
    leaf: str, lower: int, upper: int
) -> None:
    with pytest.raises(ValueError, match="routing demand"):
        RoutingDemandRange(leaf, lower, upper)
