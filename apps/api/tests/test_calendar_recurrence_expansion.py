"""Bounded expansion of a stored calendar recurrence into a review window."""

from datetime import UTC, date, datetime, timedelta

import pytest

from coeus.domain.calendar_recurrence import MAX_OCCURRENCES, expand_occurrences
from coeus.domain.workforce_calendar import (
    CalendarFrequency,
    CalendarRecurrence,
    CalendarTiming,
)

WINDOW_START = datetime(2026, 8, 3, tzinfo=UTC)
WINDOW_END = WINDOW_START + timedelta(days=28)


def _timed(day: date, hour: int = 9) -> CalendarTiming:
    start = datetime(day.year, day.month, day.day, hour, tzinfo=UTC)
    return CalendarTiming("Europe/London", starts_at=start, ends_at=start + timedelta(hours=1))


def _all_day(start: date, days: int = 1) -> CalendarTiming:
    return CalendarTiming(
        "Europe/London", all_day_start=start, all_day_end=start + timedelta(days=days)
    )


def test_a_window_must_be_a_forward_interval() -> None:
    with pytest.raises(ValueError, match="window end must follow its start"):
        expand_occurrences(_timed(date(2026, 8, 4)), None, WINDOW_END, WINDOW_START)


def test_an_unknown_stored_time_zone_fails_closed() -> None:
    timing = CalendarTiming(
        "Europe/London",
        starts_at=datetime(2026, 8, 4, 9, tzinfo=UTC),
        ends_at=datetime(2026, 8, 4, 10, tzinfo=UTC),
    )
    corrupt = CalendarTiming.__new__(CalendarTiming)
    object.__setattr__(corrupt, "time_zone", "Nowhere/Imaginary")
    for field in ("starts_at", "ends_at", "all_day_start", "all_day_end"):
        object.__setattr__(corrupt, field, getattr(timing, field))

    with pytest.raises(ValueError, match="time zone is invalid"):
        expand_occurrences(corrupt, None, WINDOW_START, WINDOW_END)


def test_a_single_event_appears_only_when_it_overlaps_the_window() -> None:
    inside = expand_occurrences(_timed(date(2026, 8, 4)), None, WINDOW_START, WINDOW_END)
    outside = expand_occurrences(_timed(date(2026, 9, 30)), None, WINDOW_START, WINDOW_END)

    assert tuple(item.occurrence_key for item in inside) == ("single",)
    assert outside == ()


def test_a_daily_recurrence_honours_its_interval_and_end_date() -> None:
    recurrence = CalendarRecurrence(CalendarFrequency.DAILY, 3, date(2026, 8, 16))

    occurrences = expand_occurrences(_timed(date(2026, 8, 4)), recurrence, WINDOW_START, WINDOW_END)

    assert [item.occurrence_key for item in occurrences] == [
        "2026-08-04",
        "2026-08-07",
        "2026-08-10",
        "2026-08-13",
        "2026-08-16",
    ]


def test_a_weekly_recurrence_selects_its_weekdays_every_nth_week() -> None:
    # Tuesdays and Thursdays, every other week, starting Tuesday 4 August.
    recurrence = CalendarRecurrence(CalendarFrequency.WEEKLY, 2, date(2026, 8, 27), (1, 3))

    occurrences = expand_occurrences(_timed(date(2026, 8, 4)), recurrence, WINDOW_START, WINDOW_END)

    assert [item.occurrence_key for item in occurrences] == [
        "2026-08-04",
        "2026-08-06",
        "2026-08-18",
        "2026-08-20",
    ]


def test_an_all_day_recurrence_keeps_its_duration_on_every_occurrence() -> None:
    recurrence = CalendarRecurrence(CalendarFrequency.DAILY, 7, date(2026, 8, 18))

    occurrences = expand_occurrences(
        _all_day(date(2026, 8, 4), days=2), recurrence, WINDOW_START, WINDOW_END
    )

    assert [item.occurrence_key for item in occurrences] == [
        "2026-08-04",
        "2026-08-11",
        "2026-08-18",
    ]
    for item in occurrences:
        assert item.timing.all_day_end is not None and item.timing.all_day_start is not None
        assert (item.timing.all_day_end - item.timing.all_day_start).days == 2


@pytest.mark.parametrize("until", [date(2026, 8, 3), date(2027, 9, 1)])
def test_a_recurrence_outside_its_supported_window_is_refused(until: date) -> None:
    recurrence = CalendarRecurrence(CalendarFrequency.DAILY, 1, until)

    with pytest.raises(ValueError, match="outside its supported window"):
        expand_occurrences(_timed(date(2026, 8, 4)), recurrence, WINDOW_START, WINDOW_END)


def test_the_366_day_recurrence_limit_keeps_expansion_under_the_ceiling() -> None:
    # The supported window is the effective bound: a daily series can only
    # reach 367 occurrences, so the 500-occurrence guard is a backstop.
    start = date(2026, 8, 4)
    recurrence = CalendarRecurrence(CalendarFrequency.DAILY, 1, start + timedelta(days=366))
    window_end = datetime(2027, 9, 1, tzinfo=UTC)

    occurrences = expand_occurrences(_timed(start), recurrence, WINDOW_START, window_end)

    assert len(occurrences) == 367 <= MAX_OCCURRENCES


def test_occurrences_before_the_window_are_dropped_but_later_ones_survive() -> None:
    recurrence = CalendarRecurrence(CalendarFrequency.DAILY, 7, date(2026, 8, 24))
    window_start = datetime(2026, 8, 15, tzinfo=UTC)

    occurrences = expand_occurrences(
        _timed(date(2026, 7, 27)), recurrence, window_start, WINDOW_END
    )

    assert [item.occurrence_key for item in occurrences] == ["2026-08-17", "2026-08-24"]
