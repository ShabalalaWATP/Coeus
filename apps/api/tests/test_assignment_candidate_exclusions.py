"""Every reason a person is excluded from an assignment recommendation."""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from coeus.domain.assignment_recommendations import (
    AssignmentDemand,
    ExclusionCode,
)
from coeus.domain.capacity_forecast import CapacityForecast
from coeus.domain.team_task_ownership import WorkflowLeg
from coeus.persistence.assignment_recommendation_ranking import (
    _candidate,
    _InternalExclusion,
    _safe_code,
)

UNIT, ANALYST = uuid4(), uuid4()
START = datetime(2026, 8, 17, 9, tzinfo=UTC)
CAPABILITY = "regional-analysis"


def _demand() -> AssignmentDemand:
    return AssignmentDemand(
        uuid4(), WorkflowLeg.RFA, 60, 120, START, START + timedelta(days=7), (CAPABILITY,)
    )


def _row(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "unit_id": UNIT,
        "user_id": ANALYST,
        "is_active": True,
        "roles": ["Analyst"],
        "assignment_eligible": True,
        "home_count": 1,
        "active_wip": 1,
        "wip_limit": 3,
        "membership_version": 2,
        "source_hash": "a" * 64,
    }
    values.update(overrides)
    return values


def _forecast(assignable: int) -> CapacityForecast:
    return CapacityForecast(480, 0, 0, 480 - assignable, 0, assignable)


def _evaluate(
    row: dict[str, object],
    forecast: CapacityForecast | None = None,
    team_caps: dict[UUID, int] | None = None,
    person_caps: dict[UUID, int] | None = None,
) -> object:
    return _candidate(
        row,  # type: ignore[arg-type]
        _demand(),
        {UNIT: 1} if team_caps is None else team_caps,
        {ANALYST: 1} if person_caps is None else person_caps,
        1,
        _forecast(240) if forecast is None else forecast,
    )


def test_an_eligible_analyst_returns_ranked_evidence() -> None:
    result = _evaluate(_row(roles=["Analyst"]))

    assert isinstance(result, tuple)
    unit_id, user_id, assignable, wip, hashed = result
    assert (unit_id, user_id, assignable, wip) == (UNIT, ANALYST, 240, 1)
    assert len(hashed) == 64


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({"is_active": False}, _InternalExclusion.ACCOUNT),
        ({"roles": []}, _InternalExclusion.ACCOUNT),
        ({"roles": None}, _InternalExclusion.ACCOUNT),
        ({"assignment_eligible": False}, _InternalExclusion.POSTING),
        ({"home_count": 2}, _InternalExclusion.POSTING),
        ({"active_wip": 3}, _InternalExclusion.WIP),
    ],
)
def test_account_posting_and_workload_exclusions(
    overrides: dict[str, object], expected: _InternalExclusion
) -> None:
    row = _row(roles=["Analyst"])
    row.update(overrides)

    assert _evaluate(row) is expected


def test_team_and_person_capability_gaps_are_reported_separately() -> None:
    row = _row(roles=["Analyst"])

    assert _evaluate(row, team_caps={}) is _InternalExclusion.CAPABILITY
    assert _evaluate(row, person_caps={}) is _InternalExclusion.COMPETENCY


def test_missing_or_insufficient_capacity_is_distinguished() -> None:
    row = _row(roles=["Analyst"])

    assert _evaluate(row, forecast=_forecast(60)) is _InternalExclusion.CAPACITY
    assert (
        _candidate(row, _demand(), {UNIT: 1}, {ANALYST: 1}, 1, None)  # type: ignore[arg-type]
        is _InternalExclusion.UNKNOWN
    )


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (_InternalExclusion.UNKNOWN, ExclusionCode.DATA_UNKNOWN),
        (_InternalExclusion.CAPACITY, ExclusionCode.CAPACITY_UNAVAILABLE),
        (_InternalExclusion.ACCOUNT, ExclusionCode.NOT_CURRENTLY_ELIGIBLE),
        (_InternalExclusion.POSTING, ExclusionCode.NOT_CURRENTLY_ELIGIBLE),
        (_InternalExclusion.CAPABILITY, ExclusionCode.NOT_CURRENTLY_ELIGIBLE),
        (_InternalExclusion.COMPETENCY, ExclusionCode.NOT_CURRENTLY_ELIGIBLE),
        (_InternalExclusion.WIP, ExclusionCode.NOT_CURRENTLY_ELIGIBLE),
    ],
)
def test_internal_reasons_are_reduced_to_three_disclosed_codes(
    value: _InternalExclusion, expected: ExclusionCode
) -> None:
    # Managers are told capacity or data is the problem, never which person
    # failed which personal check.
    assert _safe_code(value) is expected
