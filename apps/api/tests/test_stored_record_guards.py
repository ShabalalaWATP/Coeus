"""Defensive guards that refuse corrupt stored records rather than guessing.

These paths are unreachable through the domain constructors, which is the
point: they exist so that a row written by an older release, a migration or a
manual edit fails closed instead of producing a plausible wrong answer.
"""

from datetime import UTC, date, datetime, timedelta
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

import pytest

from coeus.domain.calendar_recurrence import _move_timing, _overlaps
from coeus.domain.jioc_principals import JIOC_AGENT_PRINCIPAL
from coeus.domain.work_package_handovers import (
    WorkPackageHandoverDenied,
    WorkPackageHandoverRequest,
)
from coeus.domain.workflow_leg_transfers import WorkflowLegTransferDenied
from coeus.domain.workforce_calendar import CalendarTiming
from coeus.persistence.work_package_handover_validation import _validate_target
from coeus.persistence.workflow_leg_transfer_validation import validate_target

ZONE = ZoneInfo("Europe/London")
DIGEST = "a" * 64
START = datetime(2026, 8, 17, 9, tzinfo=UTC)


def _corrupt_timing(**fields: object) -> CalendarTiming:
    timing = CalendarTiming.__new__(CalendarTiming)
    values: dict[str, object] = {
        "time_zone": "Europe/London",
        "starts_at": None,
        "ends_at": None,
        "all_day_start": None,
        "all_day_end": None,
    }
    values.update(fields)
    for name, value in values.items():
        object.__setattr__(timing, name, value)
    return timing


def test_a_recurring_seed_with_half_an_interval_is_refused() -> None:
    with pytest.raises(ValueError, match="recurring calendar timing is incomplete"):
        _move_timing(_corrupt_timing(starts_at=START), date(2026, 8, 18), ZONE)
    with pytest.raises(ValueError, match="recurring calendar timing is incomplete"):
        _move_timing(_corrupt_timing(ends_at=START), date(2026, 8, 18), ZONE)


def test_a_recurring_seed_that_ends_before_it_starts_is_refused() -> None:
    timing = _corrupt_timing(starts_at=START, ends_at=START - timedelta(hours=1))

    with pytest.raises(ValueError, match="recurring calendar timing is invalid"):
        _move_timing(timing, date(2026, 8, 18), ZONE)


def test_a_timing_that_is_neither_timed_nor_all_day_cannot_be_placed() -> None:
    with pytest.raises(ValueError, match="calendar timing is incomplete"):
        _overlaps(_corrupt_timing(), START, START + timedelta(days=1), ZONE)


def test_an_all_day_seed_keeps_its_duration_when_moved() -> None:
    timing = _corrupt_timing(all_day_start=date(2026, 8, 4), all_day_end=date(2026, 8, 6))

    moved = _move_timing(timing, date(2026, 8, 11), ZONE)

    assert moved.all_day_start == date(2026, 8, 11)
    assert moved.all_day_end == date(2026, 8, 13)


def _handover(target: UUID) -> WorkPackageHandoverRequest:
    return WorkPackageHandoverRequest(
        uuid4(), uuid4(), target, 1, 1, uuid4(), 1, uuid4(), 1, 0, DIGEST, 1, DIGEST, ()
    )


def test_a_handover_target_must_be_a_human_analyst() -> None:
    with pytest.raises(WorkPackageHandoverDenied, match="must be a human analyst"):
        _validate_target(
            object(),  # type: ignore[arg-type]
            _handover(JIOC_AGENT_PRINCIPAL),
            datetime.now(UTC),
            datetime.now(UTC) + timedelta(hours=1),
        )


def test_a_transfer_target_must_be_a_human_analyst() -> None:
    with pytest.raises(WorkflowLegTransferDenied, match="target analyst is unavailable"):
        validate_target(
            object(),  # type: ignore[arg-type]
            JIOC_AGENT_PRINCIPAL,
            uuid4(),
            uuid4(),
            1,
            0,
            DIGEST,
            START,
            START + timedelta(hours=1),
        )
