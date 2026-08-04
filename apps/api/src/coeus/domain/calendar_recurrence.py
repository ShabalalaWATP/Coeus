"""Deterministic bounded expansion of canonical calendar series."""

from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from coeus.domain.workforce_calendar import (
    CalendarEvent,
    CalendarFrequency,
    CalendarOccurrence,
    CalendarOccurrenceException,
    CalendarRecurrence,
    CalendarTiming,
)

MAX_OCCURRENCES = 500


@dataclass(frozen=True)
class ExpandedOccurrence:
    occurrence_key: str
    timing: CalendarTiming


def expand_event(
    event: CalendarEvent, window_start: datetime, window_end: datetime
) -> tuple[CalendarOccurrence, ...]:
    exceptions = {item.occurrence_key: item for item in event.exceptions}
    return tuple(
        CalendarOccurrence(
            event.event_id,
            occurrence.occurrence_key,
            _apply_exception(event, occurrence, exceptions.get(occurrence.occurrence_key)),
            event.timing,
        )
        for occurrence in expand_occurrences(
            event.timing, event.recurrence, window_start, window_end
        )
        if not (
            exceptions.get(occurrence.occurrence_key) is not None
            and exceptions[occurrence.occurrence_key].cancelled
        )
    )


def _apply_exception(
    event: CalendarEvent,
    occurrence: ExpandedOccurrence,
    exception: CalendarOccurrenceException | None,
) -> CalendarEvent:
    if exception is None:
        return replace(event, timing=occurrence.timing)
    if exception.cancelled or exception.timing is None:
        raise ValueError("cancelled calendar occurrence cannot be materialised")
    if any(
        value is None
        for value in (exception.activity, exception.availability, exception.privacy, exception.note)
    ):
        raise ValueError("changed calendar occurrence is incomplete")
    assert exception.activity is not None
    assert exception.availability is not None
    assert exception.privacy is not None
    assert exception.note is not None
    return replace(
        event,
        timing=exception.timing,
        activity=exception.activity,
        availability=exception.availability,
        privacy=exception.privacy,
        note=exception.note,
    )


def expand_occurrences(
    timing: CalendarTiming,
    recurrence: CalendarRecurrence | None,
    window_start: datetime,
    window_end: datetime,
) -> tuple[ExpandedOccurrence, ...]:
    """Expand one seed using local wall time, clipped to an aware half-open window."""
    if window_end <= window_start:
        raise ValueError("calendar window end must follow its start")
    try:
        zone = ZoneInfo(timing.time_zone)
    except ZoneInfoNotFoundError as exc:
        raise ValueError("stored calendar time zone is invalid") from exc
    if recurrence is None:
        return (
            (ExpandedOccurrence("single", timing),)
            if _overlaps(timing, window_start, window_end, zone)
            else ()
        )
    start = timing.start_date
    if recurrence.until < start or recurrence.until > start + timedelta(days=366):
        raise ValueError("stored calendar recurrence is outside its supported window")
    values: list[ExpandedOccurrence] = []
    for occurrence_date in _dates(start, recurrence):
        occurrence = ExpandedOccurrence(
            occurrence_date.isoformat(), _move_timing(timing, occurrence_date, zone)
        )
        if _overlaps(occurrence.timing, window_start, window_end, zone):
            values.append(occurrence)
            if len(values) > MAX_OCCURRENCES:
                raise ValueError("calendar recurrence exceeds 500 occurrences")
    return tuple(values)


def _dates(start: date, recurrence: CalendarRecurrence) -> tuple[date, ...]:
    if recurrence.frequency is CalendarFrequency.DAILY:
        count = ((recurrence.until - start).days // recurrence.interval) + 1
        return tuple(start + timedelta(days=index * recurrence.interval) for index in range(count))
    week_start = start - timedelta(days=start.weekday())
    return tuple(
        current
        for offset in range((recurrence.until - start).days + 1)
        if (current := start + timedelta(days=offset)).weekday() in recurrence.weekdays
        and ((current - week_start).days // 7) % recurrence.interval == 0
    )


def _move_timing(timing: CalendarTiming, day: date, zone: ZoneInfo) -> CalendarTiming:
    if timing.all_day_start is not None and timing.all_day_end is not None:
        duration = timing.all_day_end - timing.all_day_start
        return CalendarTiming(timing.time_zone, all_day_start=day, all_day_end=day + duration)
    if timing.starts_at is None or timing.ends_at is None:
        raise ValueError("recurring calendar timing is incomplete")
    local_start = timing.starts_at.astimezone(zone)
    local_end = timing.ends_at.astimezone(zone)
    end_day = day + (local_end.date() - local_start.date())
    starts_at = datetime.combine(day, local_start.timetz().replace(tzinfo=None), zone)
    ends_at = datetime.combine(end_day, local_end.timetz().replace(tzinfo=None), zone)
    if ends_at <= starts_at:
        raise ValueError("recurring calendar timing is invalid")
    return CalendarTiming(
        timing.time_zone,
        starts_at=starts_at.astimezone(UTC),
        ends_at=ends_at.astimezone(UTC),
    )


def _overlaps(
    timing: CalendarTiming, window_start: datetime, window_end: datetime, zone: ZoneInfo
) -> bool:
    if timing.all_day_start is not None and timing.all_day_end is not None:
        starts_at = datetime.combine(timing.all_day_start, time.min, zone).astimezone(UTC)
        ends_at = datetime.combine(timing.all_day_end, time.min, zone).astimezone(UTC)
    elif timing.starts_at is not None and timing.ends_at is not None:
        starts_at, ends_at = timing.starts_at, timing.ends_at
    else:
        raise ValueError("calendar timing is incomplete")
    return starts_at < window_end and ends_at > window_start
