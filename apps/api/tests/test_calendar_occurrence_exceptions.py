"""Per-occurrence exceptions applied while expanding a recurring event."""

from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest

from coeus.domain.calendar_recurrence import expand_event
from coeus.domain.workforce_calendar import (
    AvailabilityEffect,
    CalendarActivity,
    CalendarEvent,
    CalendarEventSource,
    CalendarFrequency,
    CalendarOccurrenceException,
    CalendarPrivacy,
    CalendarRecurrence,
    CalendarTiming,
)

WINDOW_START = datetime(2026, 8, 3, tzinfo=UTC)
WINDOW_END = WINDOW_START + timedelta(days=21)
OWNER = uuid4()


def _timing(day: date, hour: int = 9) -> CalendarTiming:
    start = datetime(day.year, day.month, day.day, hour, tzinfo=UTC)
    return CalendarTiming("Europe/London", starts_at=start, ends_at=start + timedelta(hours=1))


def _event(*exceptions: CalendarOccurrenceException) -> CalendarEvent:
    return CalendarEvent(
        uuid4(),
        OWNER,
        CalendarEventSource.PERSONAL,
        CalendarActivity.TRAINING,
        _timing(date(2026, 8, 4)),
        AvailabilityEffect.PARTIAL,
        CalendarPrivacy.PRIVATE,
        OWNER,
        "Weekly training",
        CalendarRecurrence(CalendarFrequency.DAILY, 7, date(2026, 8, 18)),
        exceptions=exceptions,
    )


def _change(day: date) -> CalendarOccurrenceException:
    return CalendarOccurrenceException(
        day.isoformat(),
        False,
        _timing(day, hour=14),
        CalendarActivity.LEAVE,
        AvailabilityEffect.UNAVAILABLE,
        CalendarPrivacy.TEAM_DETAIL,
        "Rescheduled to the afternoon.",
    )


def test_an_event_without_exceptions_repeats_its_own_details() -> None:
    occurrences = expand_event(_event(), WINDOW_START, WINDOW_END)

    assert [item.occurrence_key for item in occurrences] == [
        "2026-08-04",
        "2026-08-11",
        "2026-08-18",
    ]
    assert all(item.event.activity is CalendarActivity.TRAINING for item in occurrences)
    assert all(item.series_event_id == occurrences[0].series_event_id for item in occurrences)


def test_a_cancelled_occurrence_is_dropped_from_the_expansion() -> None:
    event = _event(CalendarOccurrenceException("2026-08-11", True))

    occurrences = expand_event(event, WINDOW_START, WINDOW_END)

    assert [item.occurrence_key for item in occurrences] == ["2026-08-04", "2026-08-18"]


def test_a_changed_occurrence_carries_its_own_details_and_timing() -> None:
    event = _event(_change(date(2026, 8, 11)))

    occurrences = expand_event(event, WINDOW_START, WINDOW_END)
    changed = next(item for item in occurrences if item.occurrence_key == "2026-08-11")
    unchanged = next(item for item in occurrences if item.occurrence_key == "2026-08-04")

    assert changed.event.activity is CalendarActivity.LEAVE
    assert changed.event.availability is AvailabilityEffect.UNAVAILABLE
    assert changed.event.privacy is CalendarPrivacy.TEAM_DETAIL
    assert changed.event.note == "Rescheduled to the afternoon."
    assert changed.event.timing.starts_at == datetime(2026, 8, 11, 14, tzinfo=UTC)
    assert changed.series_timing == unchanged.series_timing


def test_an_exception_must_be_a_cancellation_or_a_complete_change() -> None:
    with pytest.raises(ValueError, match="cancellation or complete change"):
        CalendarOccurrenceException("2026-08-11", False)
    with pytest.raises(ValueError, match="cancellation or complete change"):
        CalendarOccurrenceException(
            "2026-08-11", False, _timing(date(2026, 8, 11)), CalendarActivity.LEAVE
        )
    with pytest.raises(ValueError, match="cancellation or complete change"):
        CalendarOccurrenceException(
            "2026-08-11",
            True,
            _timing(date(2026, 8, 11)),
            CalendarActivity.LEAVE,
            AvailabilityEffect.UNAVAILABLE,
            CalendarPrivacy.TEAM_DETAIL,
            "Both at once.",
        )


def test_exception_keys_must_be_dates_and_must_not_repeat() -> None:
    with pytest.raises(ValueError):
        CalendarOccurrenceException("not-a-date", True)
    with pytest.raises(ValueError, match="unique occurrence keys"):
        _event(
            CalendarOccurrenceException("2026-08-11", True),
            CalendarOccurrenceException("2026-08-11", True),
        )


def test_an_exception_for_a_date_outside_the_series_changes_nothing() -> None:
    event = _event(_change(date(2026, 8, 12)))

    occurrences = expand_event(event, WINDOW_START, WINDOW_END)

    assert [item.occurrence_key for item in occurrences] == [
        "2026-08-04",
        "2026-08-11",
        "2026-08-18",
    ]
    assert all(item.event.activity is CalendarActivity.TRAINING for item in occurrences)
