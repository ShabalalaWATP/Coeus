from datetime import UTC, date, datetime

import pytest

from coeus.domain.capacity_forecast import CapacityInterval
from coeus.domain.work_packages import CapacityUnknown
from coeus.persistence.calendar_capacity_expansion import capacity_intervals


def _timed_row(**changes: object) -> dict[str, object]:
    row: dict[str, object] = {
        "starts_at": datetime(2026, 3, 27, 9, tzinfo=UTC),
        "ends_at": datetime(2026, 3, 27, 10, tzinfo=UTC),
        "all_day_start": None,
        "all_day_end": None,
        "time_zone": "Europe/London",
        "availability_effect": "unavailable",
        "recurrence_rule": {
            "frequency": "daily",
            "interval": 1,
            "until": "2026-03-30",
            "weekdays": [],
        },
        "exception_rows": None,
    }
    row.update(changes)
    return row


def test_daily_timed_recurrence_preserves_local_wall_time_across_dst() -> None:
    intervals = capacity_intervals(
        _timed_row(),
        datetime(2026, 3, 27, tzinfo=UTC),
        datetime(2026, 3, 31, tzinfo=UTC),
    )
    assert intervals == (
        CapacityInterval(
            datetime(2026, 3, 27, 9, tzinfo=UTC), datetime(2026, 3, 27, 10, tzinfo=UTC)
        ),
        CapacityInterval(
            datetime(2026, 3, 28, 9, tzinfo=UTC), datetime(2026, 3, 28, 10, tzinfo=UTC)
        ),
        CapacityInterval(
            datetime(2026, 3, 29, 8, tzinfo=UTC), datetime(2026, 3, 29, 9, tzinfo=UTC)
        ),
        CapacityInterval(
            datetime(2026, 3, 30, 8, tzinfo=UTC), datetime(2026, 3, 30, 9, tzinfo=UTC)
        ),
    )


def test_weekly_recurrence_honours_weekdays_interval_and_window() -> None:
    row = _timed_row(
        recurrence_rule={
            "frequency": "weekly",
            "interval": 2,
            "until": "2026-04-17",
            "weekdays": [0, 4],
        }
    )
    intervals = capacity_intervals(
        row,
        datetime(2026, 4, 9, tzinfo=UTC),
        datetime(2026, 4, 18, tzinfo=UTC),
    )
    assert intervals == (
        CapacityInterval(
            datetime(2026, 4, 10, 8, tzinfo=UTC), datetime(2026, 4, 10, 9, tzinfo=UTC)
        ),
    )


def test_all_day_recurrence_uses_local_midnight_and_duration() -> None:
    row = _timed_row(
        starts_at=None,
        ends_at=None,
        all_day_start=date(2026, 3, 28),
        all_day_end=date(2026, 3, 30),
        recurrence_rule={
            "frequency": "daily",
            "interval": 2,
            "until": "2026-03-30",
            "weekdays": [],
        },
    )
    assert capacity_intervals(
        row,
        datetime(2026, 3, 27, tzinfo=UTC),
        datetime(2026, 4, 2, tzinfo=UTC),
    ) == (
        CapacityInterval(datetime(2026, 3, 28, tzinfo=UTC), datetime(2026, 3, 29, 23, tzinfo=UTC)),
        CapacityInterval(
            datetime(2026, 3, 29, 23, tzinfo=UTC),
            datetime(2026, 3, 31, 23, tzinfo=UTC),
        ),
    )


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        (
            {
                "exception_rows": [
                    {"occurrence_key": "2026-03-28", "action": "change", "replacement": None}
                ]
            },
            "invalid",
        ),
        ({"recurrence_rule": {"frequency": "monthly"}}, "invalid"),
        (
            {
                "recurrence_rule": {
                    "frequency": "daily",
                    "interval": 1,
                    "until": "2027-04-01",
                    "weekdays": [],
                }
            },
            "supported window",
        ),
    ],
)
def test_recurrence_corruption_and_malformed_exceptions_fail_closed(
    changes: dict[str, object], message: str
) -> None:
    with pytest.raises(CapacityUnknown, match=message):
        capacity_intervals(
            _timed_row(**changes),
            datetime(2026, 3, 27, tzinfo=UTC),
            datetime(2026, 4, 1, tzinfo=UTC),
        )


def test_capacity_applies_cancelled_and_changed_occurrences() -> None:
    intervals = capacity_intervals(
        _timed_row(
            exception_rows=[
                {"occurrence_key": "2026-03-28", "action": "cancel", "replacement": None},
                {
                    "occurrence_key": "2026-03-29",
                    "action": "change",
                    "replacement": {
                        "activity": "duty",
                        "availability": "partial",
                        "privacy": "private",
                        "note": "Short duty",
                        "timing": {
                            "time_zone": "Europe/London",
                            "starts_at": "2026-03-29T12:00:00+00:00",
                            "ends_at": "2026-03-29T14:00:00+00:00",
                            "all_day_start": None,
                            "all_day_end": None,
                        },
                    },
                },
            ]
        ),
        datetime(2026, 3, 27, tzinfo=UTC),
        datetime(2026, 3, 31, tzinfo=UTC),
    )
    assert intervals[1] == CapacityInterval(
        datetime(2026, 3, 29, 12, tzinfo=UTC), datetime(2026, 3, 29, 14, tzinfo=UTC)
    )
    assert len(intervals) == 3


def test_occurrence_availability_can_restore_or_remove_capacity() -> None:
    replacement = {
        "activity": "duty",
        "privacy": "private",
        "note": "Exact availability",
        "timing": {
            "time_zone": "Europe/London",
            "starts_at": "2026-03-29T12:00:00+00:00",
            "ends_at": "2026-03-29T14:00:00+00:00",
            "all_day_start": None,
            "all_day_end": None,
        },
    }
    restored = capacity_intervals(
        _timed_row(
            exception_rows=[
                {
                    "occurrence_key": "2026-03-29",
                    "action": "change",
                    "replacement": {**replacement, "availability": "available"},
                }
            ]
        ),
        datetime(2026, 3, 29, tzinfo=UTC),
        datetime(2026, 3, 30, tzinfo=UTC),
    )
    assert restored == ()
    blocked = capacity_intervals(
        _timed_row(
            availability_effect="available",
            exception_rows=[
                {
                    "occurrence_key": "2026-03-29",
                    "action": "change",
                    "replacement": {**replacement, "availability": "partial"},
                }
            ],
        ),
        datetime(2026, 3, 29, tzinfo=UTC),
        datetime(2026, 3, 30, tzinfo=UTC),
    )
    assert blocked == (
        CapacityInterval(
            datetime(2026, 3, 29, 12, tzinfo=UTC), datetime(2026, 3, 29, 14, tzinfo=UTC)
        ),
    )


def test_incomplete_timing_and_non_overlapping_single_event_are_safe() -> None:
    with pytest.raises(CapacityUnknown, match="timing is incomplete"):
        capacity_intervals(
            _timed_row(starts_at=None, ends_at=None, recurrence_rule=None),
            datetime(2026, 3, 27, tzinfo=UTC),
            datetime(2026, 4, 1, tzinfo=UTC),
        )
    assert (
        capacity_intervals(
            _timed_row(recurrence_rule=None),
            datetime(2026, 4, 1, tzinfo=UTC),
            datetime(2026, 4, 2, tzinfo=UTC),
        )
        == ()
    )
