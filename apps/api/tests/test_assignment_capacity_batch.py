"""Bounded, fail-safe personal capacity evidence for a ranked cohort."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from coeus.persistence.assignment_capacity_batch import (
    MAX_BATCH_CANDIDATES,
    MAX_EVIDENCE_ROWS_PER_PERSON,
    _reduction_minutes,
    _safe_forecast,
    batch_person_forecasts,
)

START = datetime(2026, 8, 17, 0, tzinfo=UTC)
END = START + timedelta(days=5)


def _pattern(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "time_zone": "Europe/London",
        "monday_minutes": 480,
        "tuesday_minutes": 480,
        "wednesday_minutes": 480,
        "thursday_minutes": 480,
        "friday_minutes": 480,
        "saturday_minutes": 0,
        "sunday_minutes": 0,
    }
    values.update(overrides)
    return values


def test_an_empty_cohort_needs_no_queries() -> None:
    assert batch_person_forecasts(object(), (), START, END) == {}  # type: ignore[arg-type]


def test_an_oversized_cohort_is_refused_before_any_query() -> None:
    ids = tuple(uuid4() for _ in range(MAX_BATCH_CANDIDATES + 1))

    with pytest.raises(ValueError, match="cohort is too large"):
        batch_person_forecasts(object(), ids, START, END)  # type: ignore[arg-type]


def test_a_full_working_week_forecasts_its_physical_minutes() -> None:
    forecast = _safe_forecast((_pattern(),), (), 0, (), START, END, 0)  # type: ignore[arg-type]

    assert forecast is not None
    assert forecast.physical_minutes == 5 * 480
    assert forecast.assignable_minutes == 5 * 480


def test_reserved_minutes_and_a_buffer_reduce_what_can_be_assigned() -> None:
    forecast = _safe_forecast((_pattern(),), (), 600, (), START, END, 120)  # type: ignore[arg-type]

    assert forecast is not None
    assert forecast.reservation_minutes == 600
    assert forecast.assignable_minutes == 5 * 480 - 600 - 120


@pytest.mark.parametrize(
    "patterns",
    [(), ({"time_zone": "Europe/London"}, {"time_zone": "Europe/London"})],
)
def test_capacity_is_unknown_without_exactly_one_covering_pattern(
    patterns: tuple[dict[str, object], ...],
) -> None:
    assert _safe_forecast(patterns, (), 0, (), START, END, 0) is None  # type: ignore[arg-type]


def test_an_unusable_pattern_reports_unknown_rather_than_guessing() -> None:
    assert (
        _safe_forecast(  # type: ignore[arg-type]
            (_pattern(time_zone="Nowhere/Imaginary"),), (), 0, (), START, END, 0
        )
        is None
    )
    assert (
        _safe_forecast((_pattern(monday_minutes=None),), (), 0, (), START, END, 0)  # type: ignore[arg-type]
        is None
    )


@pytest.mark.parametrize("field", ["events", "exceptions"])
def test_oversized_personal_evidence_reports_unknown(field: str) -> None:
    oversized = tuple({} for _ in range(MAX_EVIDENCE_ROWS_PER_PERSON + 1))
    events = oversized if field == "events" else ()
    exceptions = oversized if field == "exceptions" else ()

    assert (
        _safe_forecast((_pattern(),), events, 0, exceptions, START, END, 0)  # type: ignore[arg-type]
        is None
    )


def test_a_percentage_reduction_rounds_up_to_a_whole_quarter_hour() -> None:
    rows = ({"reduction_minutes": None, "reduction_percent": 10},)

    # 10 per cent of 100 minutes is 10, which rounds up to one 15-minute block.
    assert _reduction_minutes(rows, 100) == 15  # type: ignore[arg-type]


def test_explicit_and_proportional_reductions_add_up_but_never_exceed_capacity() -> None:
    rows = (
        {"reduction_minutes": 90, "reduction_percent": None},
        {"reduction_minutes": None, "reduction_percent": 25},
    )

    assert _reduction_minutes(rows, 480) == 90 + 120  # type: ignore[arg-type]
    assert _reduction_minutes(rows, 60) == 60  # type: ignore[arg-type]
