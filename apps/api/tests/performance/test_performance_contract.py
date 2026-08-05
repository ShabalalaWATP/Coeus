"""Fast contract tests for heavy performance evidence."""

from collections.abc import Callable

import pytest

from coeus.persistence.assignment_recommendation_ranking import (
    MAX_EVALUATED_CANDIDATES,
    MAX_RETURNED_CANDIDATES,
)
from performance.performance_contract import (
    BENCHMARKS,
    REFERENCE_PROFILE,
    REPORT_SCHEMA_VERSION,
    FixtureScale,
    validate_report,
)

pytestmark = pytest.mark.performance


def _report() -> dict[str, object]:
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "reference_profile": REFERENCE_PROFILE,
        "cold_cache_observation": {"controlled": False},
        "fixture": FixtureScale().as_dict(),
        "benchmarks": [
            {
                "name": contract.name,
                "budget_ms": contract.budget_ms,
                "result_limit": contract.result_limit,
                "warm_samples": 20,
                "first_execution_ms": 1.0,
                "warm_p50_ms": 1.0,
                "warm_p95_ms": 2.0,
                "warm_max_ms": 3.0,
                "passed": True,
            }
            for contract in BENCHMARKS
        ],
        "passed": True,
    }


def test_approved_scale_and_budgets_are_fixed() -> None:
    FixtureScale().validate()
    assert FixtureScale().candidates == MAX_EVALUATED_CANDIDATES
    assert MAX_RETURNED_CANDIDATES == 10
    assert FixtureScale().as_dict() == {
        "units": 1_000,
        "memberships": 10_000,
        "calendar_events": 50_000,
        "active_cards": 10_000,
        "candidates": 500,
    }
    assert {item.name: item.budget_ms for item in BENCHMARKS} == {
        "tree_roster_100": 300.0,
        "board_100": 500.0,
        "descendant_calendar_capacity_31d": 750.0,
        "recommendation_preview_500": 1_000.0,
        "assignment_commit": 1_000.0,
    }


def test_report_contract_accepts_complete_evidence() -> None:
    validate_report(_report())


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda report: report.update(schema_version="old"), "schema"),
        (lambda report: report.pop("cold_cache_observation"), "cold-cache"),
        (lambda report: report["fixture"].update(units=999), "minimum"),  # type: ignore[union-attr]
        (
            lambda report: report["benchmarks"][0].update(budget_ms=301),  # type: ignore[index,union-attr]
            "budget",
        ),
        (
            lambda report: report["benchmarks"][0].update(warm_samples=19),  # type: ignore[index,union-attr]
            "samples",
        ),
        (
            lambda report: report["benchmarks"][0].update(passed=False),  # type: ignore[index,union-attr]
            "pass state",
        ),
    ],
)
def test_report_contract_rejects_weakened_evidence(
    mutation: Callable[[dict[str, object]], None], message: str
) -> None:
    report = _report()
    mutation(report)
    with pytest.raises(ValueError, match=message):
        validate_report(report)
