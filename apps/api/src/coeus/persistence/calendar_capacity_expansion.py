"""Capacity adapter for the shared bounded calendar-series expander."""

from collections.abc import Mapping
from datetime import UTC, date, datetime, time
from typing import Any, cast
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from coeus.domain.calendar_recurrence import expand_occurrences
from coeus.domain.capacity_forecast import CapacityInterval
from coeus.domain.work_packages import CapacityUnknown
from coeus.domain.workforce_calendar import CalendarTiming
from coeus.persistence.workforce_calendar_rows import decode_exceptions, decode_recurrence


def capacity_intervals(
    row: Mapping[str, Any],
    window_start: datetime,
    window_end: datetime,
) -> tuple[CapacityInterval, ...]:
    try:
        timing = _timing(row)
        recurrence = decode_recurrence(row.get("recurrence_rule"))
        exceptions = {
            item.occurrence_key: item for item in decode_exceptions(row.get("exception_rows"))
        }
        return tuple(
            _interval(_effective_timing(occurrence.timing, exception))
            for occurrence in expand_occurrences(timing, recurrence, window_start, window_end)
            if _blocks_capacity(
                str(row.get("availability_effect", "unavailable")),
                (exception := exceptions.get(occurrence.occurrence_key)),
            )
        )
    except ZoneInfoNotFoundError as exc:
        raise CapacityUnknown("stored calendar time zone is invalid") from exc
    except (KeyError, TypeError) as exc:
        raise CapacityUnknown("stored calendar recurrence is invalid") from exc
    except ValueError as exc:
        message = str(exc)
        if (
            "supported window" in message
            or "time zone" in message
            or "time_zone" in message
            or "timing is incomplete" in message
        ):
            if "time_zone" in message:
                raise CapacityUnknown("stored calendar time zone is invalid") from exc
            raise CapacityUnknown(message) from exc
        raise CapacityUnknown("stored calendar recurrence is invalid") from exc


def _timing(row: Mapping[str, Any]) -> CalendarTiming:
    timed = isinstance(row.get("starts_at"), datetime) and isinstance(row.get("ends_at"), datetime)
    all_day = isinstance(row.get("all_day_start"), date) and isinstance(
        row.get("all_day_end"), date
    )
    if timed == all_day:
        raise ValueError("calendar timing is incomplete")
    return CalendarTiming(
        str(row.get("time_zone")),
        cast(datetime | None, row.get("starts_at")),
        cast(datetime | None, row.get("ends_at")),
        cast(date | None, row.get("all_day_start")),
        cast(date | None, row.get("all_day_end")),
    )


def _effective_timing(timing: CalendarTiming, exception: Any) -> CalendarTiming:
    if exception is None:
        return timing
    if not isinstance(exception.timing, CalendarTiming):
        raise ValueError("stored calendar exception timing is invalid")
    return exception.timing


def _blocks_capacity(base_effect: str, exception: Any) -> bool:
    if exception is None:
        return base_effect in {"partial", "unavailable"}
    if exception.cancelled:
        return False
    return str(exception.availability) in {"partial", "unavailable"}


def _interval(timing: CalendarTiming) -> CapacityInterval:
    if timing.starts_at is not None and timing.ends_at is not None:
        return CapacityInterval(timing.starts_at, timing.ends_at)
    if timing.all_day_start is None or timing.all_day_end is None:
        raise ValueError("calendar timing is incomplete")
    zone = ZoneInfo(timing.time_zone)
    return CapacityInterval(
        datetime.combine(timing.all_day_start, time.min, zone).astimezone(UTC),
        datetime.combine(timing.all_day_end, time.min, zone).astimezone(UTC),
    )
