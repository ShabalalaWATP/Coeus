"""Bounded calendar and workforce evidence for capacity reservations."""

from datetime import UTC, datetime, time, timedelta
from decimal import ROUND_CEILING, Decimal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import text
from sqlalchemy.engine import Connection, RowMapping

from coeus.domain.capacity_forecast import CapacityInterval
from coeus.domain.work_packages import CapacityUnknown, ReserveCapacityCommand
from coeus.persistence.calendar_capacity_expansion import capacity_intervals
from coeus.persistence.capacity_reservation_sql import (
    CALENDAR,
    DAYS,
    EXCEPTIONS,
    PATTERN,
    RESERVED,
)


def working_pattern(connection: Connection, command: ReserveCapacityCommand) -> RowMapping:
    rows = tuple(
        connection.execute(
            text(PATTERN),
            {"user_id": command.user_id, "start": command.starts_at, "end": command.ends_at},
        ).mappings()
    )
    if len(rows) != 1:
        raise CapacityUnknown("one working pattern must cover the reservation interval")
    return rows[0]


def working_intervals(
    pattern: RowMapping, starts_at: datetime, ends_at: datetime
) -> tuple[CapacityInterval, ...]:
    try:
        zone = ZoneInfo(str(pattern["time_zone"]))
    except ZoneInfoNotFoundError as exc:
        raise CapacityUnknown("working pattern time zone is invalid") from exc
    local_start, local_end = starts_at.astimezone(zone), ends_at.astimezone(zone)
    minutes = tuple(int(pattern[f"{day}_minutes"]) for day in DAYS)
    intervals: list[CapacityInterval] = []
    current = local_start.date()
    while current <= local_end.date():
        duration = minutes[current.weekday()]
        if duration:
            shift_start = datetime.combine(current, time(9), zone)
            shift_end = shift_start + timedelta(minutes=duration)
            start = max(starts_at, shift_start.astimezone(UTC))
            end = min(ends_at, shift_end.astimezone(UTC))
            if start < end:
                intervals.append(CapacityInterval(start, end))
        current += timedelta(days=1)
    if not intervals:
        raise CapacityUnknown("working pattern has no capacity in the requested interval")
    return tuple(intervals)


def calendar_intervals(
    connection: Connection, command: ReserveCapacityCommand
) -> tuple[CapacityInterval, ...]:
    rows = tuple(
        connection.execute(
            text(CALENDAR),
            {"user_id": command.user_id, "start": command.starts_at, "end": command.ends_at},
        ).mappings()
    )
    if len(rows) > 500:
        raise CapacityUnknown("calendar capacity window is too large")
    intervals: list[CapacityInterval] = []
    for row in rows:
        intervals.extend(capacity_intervals(dict(row), command.starts_at, command.ends_at))
    return tuple(intervals)


def existing_reservation_minutes(connection: Connection, command: ReserveCapacityCommand) -> int:
    value = connection.execute(
        text(RESERVED),
        {"user_id": command.user_id, "start": command.starts_at, "end": command.ends_at},
    ).scalar_one()
    return int(value or 0)


def exception_minutes(
    connection: Connection, command: ReserveCapacityCommand, physical_minutes: int
) -> int:
    rows = connection.execute(
        text(EXCEPTIONS),
        {"user_id": command.user_id, "start": command.starts_at, "end": command.ends_at},
    ).mappings()
    total = 0
    for row in rows:
        if row["reduction_minutes"] is not None:
            total += int(row["reduction_minutes"])
        else:
            raw = Decimal(physical_minutes) * Decimal(row["reduction_percent"]) / Decimal(100)
            total += int((raw / Decimal(15)).to_integral_value(rounding=ROUND_CEILING)) * 15
    return min(physical_minutes, total)
