"""Versioned contract for the Sprint 24 reference performance gate."""

from dataclasses import dataclass

REPORT_SCHEMA_VERSION = "coeus.sprint24.performance.v1"
REFERENCE_PROFILE = "github-actions-ubuntu-24.04-postgresql-16-v1"


@dataclass(frozen=True)
class FixtureScale:
    units: int = 1_000
    memberships: int = 10_000
    calendar_events: int = 50_000
    active_cards: int = 10_000
    candidates: int = 500

    def validate(self) -> None:
        minimums = FixtureScale()
        for field_name in ("units", "memberships", "calendar_events", "active_cards"):
            if getattr(self, field_name) < getattr(minimums, field_name):
                raise ValueError(f"{field_name} is below the approved minimum")
        if self.candidates != 500:
            raise ValueError("the recommendation cohort must contain exactly 500 candidates")

    def as_dict(self) -> dict[str, int]:
        return {
            "units": self.units,
            "memberships": self.memberships,
            "calendar_events": self.calendar_events,
            "active_cards": self.active_cards,
            "candidates": self.candidates,
        }


@dataclass(frozen=True)
class BenchmarkContract:
    name: str
    budget_ms: float
    result_limit: int | None


BENCHMARKS = (
    BenchmarkContract("tree_roster_100", 300.0, 100),
    BenchmarkContract("board_100", 500.0, 100),
    BenchmarkContract("descendant_calendar_capacity_31d", 750.0, None),
    BenchmarkContract("recommendation_preview_500", 1_000.0, 500),
    BenchmarkContract("assignment_commit", 1_000.0, 1),
)


def validate_report(report: dict[str, object]) -> None:
    """Reject incomplete or weakened machine-readable evidence."""

    if report.get("schema_version") != REPORT_SCHEMA_VERSION:
        raise ValueError("unsupported performance report schema")
    if report.get("reference_profile") != REFERENCE_PROFILE:
        raise ValueError("unexpected performance reference profile")
    cold_observation = report.get("cold_cache_observation")
    if not isinstance(cold_observation, dict) or "controlled" not in cold_observation:
        raise ValueError("cold-cache observation method is missing")
    fixture = report.get("fixture")
    if not isinstance(fixture, dict):
        raise ValueError("fixture cardinalities are missing")
    scale = FixtureScale(**{key: int(value) for key, value in fixture.items()})
    scale.validate()
    results = report.get("benchmarks")
    if not isinstance(results, list):
        raise ValueError("benchmark results are missing")
    by_name = {str(result.get("name")): result for result in results if isinstance(result, dict)}
    expected_names = {contract.name for contract in BENCHMARKS}
    if len(by_name) != len(results) or set(by_name) != expected_names:
        raise ValueError("benchmark result set is invalid")
    for contract in BENCHMARKS:
        result = by_name.get(contract.name)
        if result is None:
            raise ValueError(f"missing benchmark: {contract.name}")
        if float(result.get("budget_ms", -1)) != contract.budget_ms:
            raise ValueError(f"budget was changed for {contract.name}")
        if result.get("result_limit") != contract.result_limit:
            raise ValueError(f"result limit was changed for {contract.name}")
        if int(result.get("warm_samples", 0)) < 20:
            raise ValueError(f"insufficient warm samples for {contract.name}")
        for field_name in ("first_execution_ms", "warm_p50_ms", "warm_p95_ms", "warm_max_ms"):
            if not isinstance(result.get(field_name), (int, float)):
                raise ValueError(f"missing {field_name} for {contract.name}")
        expected_pass = float(result["warm_p95_ms"]) <= contract.budget_ms
        if result.get("passed") is not expected_pass:
            raise ValueError(f"inconsistent pass state for {contract.name}")
    expected_overall = all(bool(result["passed"]) for result in by_name.values())
    if report.get("passed") is not expected_overall:
        raise ValueError("inconsistent overall performance pass state")
