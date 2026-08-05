from datetime import UTC, date, datetime
from uuid import uuid4

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


def _event(timing: CalendarTiming, recurrence: CalendarRecurrence) -> CalendarEvent:
    owner = uuid4()
    return CalendarEvent(
        uuid4(),
        owner,
        CalendarEventSource.PERSONAL,
        CalendarActivity.TRAINING,
        timing,
        AvailabilityEffect.UNAVAILABLE,
        CalendarPrivacy.TEAM_SUMMARY,
        owner,
        recurrence=recurrence,
    )


def test_timed_occurrences_preserve_wall_time_and_stable_identity_across_dst() -> None:
    event = _event(
        CalendarTiming(
            "Europe/London",
            datetime(2026, 3, 27, 9, tzinfo=UTC),
            datetime(2026, 3, 27, 10, tzinfo=UTC),
        ),
        CalendarRecurrence(CalendarFrequency.DAILY, 1, date(2026, 3, 30)),
    )
    occurrences = expand_event(
        event, datetime(2026, 3, 28, tzinfo=UTC), datetime(2026, 3, 31, tzinfo=UTC)
    )
    assert [item.occurrence_key for item in occurrences] == [
        "2026-03-28",
        "2026-03-29",
        "2026-03-30",
    ]
    assert all(item.series_event_id == event.event_id for item in occurrences)
    assert occurrences[1].event.timing.starts_at == datetime(2026, 3, 29, 8, tzinfo=UTC)
    assert occurrences[1].series_timing == event.timing


def test_weekly_all_day_occurrences_are_clipped_to_the_requested_window() -> None:
    event = _event(
        CalendarTiming(
            "Europe/London", all_day_start=date(2026, 3, 2), all_day_end=date(2026, 3, 3)
        ),
        CalendarRecurrence(CalendarFrequency.WEEKLY, 2, date(2026, 3, 31), (0, 2)),
    )
    occurrences = expand_event(
        event, datetime(2026, 3, 10, tzinfo=UTC), datetime(2026, 3, 20, tzinfo=UTC)
    )
    assert [item.occurrence_key for item in occurrences] == ["2026-03-16", "2026-03-18"]


def test_cancelled_and_changed_occurrences_are_applied_without_changing_series_identity() -> None:
    event = _event(
        CalendarTiming(
            "Europe/London", all_day_start=date(2026, 3, 2), all_day_end=date(2026, 3, 3)
        ),
        CalendarRecurrence(CalendarFrequency.DAILY, 1, date(2026, 3, 4)),
    )
    changed = CalendarTiming(
        "Europe/London",
        datetime(2026, 3, 4, 13, tzinfo=UTC),
        datetime(2026, 3, 4, 15, tzinfo=UTC),
    )
    event = event.__class__(
        **{
            **vars(event),
            "exceptions": (
                CalendarOccurrenceException("2026-03-03", True),
                CalendarOccurrenceException(
                    "2026-03-04",
                    False,
                    changed,
                    CalendarActivity.DUTY,
                    AvailabilityEffect.PARTIAL,
                    CalendarPrivacy.PRIVATE,
                    "Changed safely",
                ),
            ),
        }
    )
    occurrences = expand_event(
        event, datetime(2026, 3, 1, tzinfo=UTC), datetime(2026, 3, 6, tzinfo=UTC)
    )
    assert [item.occurrence_key for item in occurrences] == ["2026-03-02", "2026-03-04"]
    assert occurrences[1].event.timing == changed
    assert occurrences[1].event.availability is AvailabilityEffect.PARTIAL
    assert occurrences[1].series_event_id == event.event_id
