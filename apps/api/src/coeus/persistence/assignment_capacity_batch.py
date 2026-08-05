"""Bounded, set-based personal capacity evidence for assignment ranking."""

from collections import defaultdict
from collections.abc import Iterable
from datetime import datetime
from decimal import ROUND_CEILING, Decimal
from uuid import UUID
from zoneinfo import ZoneInfoNotFoundError

from sqlalchemy import text
from sqlalchemy.engine import Connection, RowMapping

from coeus.domain.capacity_forecast import CapacityForecast, forecast_capacity
from coeus.persistence.calendar_capacity_expansion import capacity_intervals
from coeus.persistence.team_capacity_forecast_postgres import _working_intervals

MAX_BATCH_CANDIDATES = 500
MAX_EVIDENCE_ROWS_PER_PERSON = 500


def batch_person_forecasts(
    connection: Connection,
    user_ids: tuple[UUID, ...],
    start: datetime,
    end: datetime,
    buffer_minutes: int = 0,
) -> dict[UUID, CapacityForecast | None]:
    """Load a bounded cohort in four set queries, independent of cohort size."""

    unique_ids = tuple(dict.fromkeys(user_ids))
    if len(unique_ids) > MAX_BATCH_CANDIDATES:
        raise ValueError("capacity forecast cohort is too large")
    if not unique_ids:
        return {}
    parameters = {"user_ids": list(unique_ids), "start": start, "end": end}
    patterns = _group(connection.execute(text(_PATTERNS), parameters).mappings(), "user_id")
    events = _group(connection.execute(text(_EVENTS), parameters).mappings(), "user_id")
    reservations = {
        UUID(str(row["user_id"])): int(row["reserved_minutes"] or 0)
        for row in connection.execute(text(_RESERVATIONS), parameters).mappings()
    }
    exceptions = _group(connection.execute(text(_EXCEPTIONS), parameters).mappings(), "user_id")
    return {
        user_id: _safe_forecast(
            patterns.get(user_id, ()),
            events.get(user_id, ()),
            reservations.get(user_id, 0),
            exceptions.get(user_id, ()),
            start,
            end,
            buffer_minutes,
        )
        for user_id in unique_ids
    }


def _group(rows: Iterable[RowMapping], key: str) -> dict[UUID, tuple[RowMapping, ...]]:
    grouped: defaultdict[UUID, list[RowMapping]] = defaultdict(list)
    for row in rows:
        grouped[UUID(str(row[key]))].append(row)
    return {user_id: tuple(values) for user_id, values in grouped.items()}


def _safe_forecast(
    patterns: tuple[RowMapping, ...],
    events: tuple[RowMapping, ...],
    reserved: int,
    exceptions: tuple[RowMapping, ...],
    start: datetime,
    end: datetime,
    buffer_minutes: int,
) -> CapacityForecast | None:
    try:
        if len(patterns) != 1:
            raise ValueError("one pattern must cover the interval")
        if len(events) > MAX_EVIDENCE_ROWS_PER_PERSON:
            raise ValueError("calendar evidence is too large")
        if len(exceptions) > MAX_EVIDENCE_ROWS_PER_PERSON:
            raise ValueError("capacity exception evidence is too large")
        working = _working_intervals(patterns[0], start, end)
        unavailable = tuple(
            interval for row in events for interval in capacity_intervals(dict(row), start, end)
        )
        physical = forecast_capacity(working, unavailable, (), 0, 0).physical_minutes
        reductions = _reduction_minutes(exceptions, physical)
        return forecast_capacity(working, unavailable, (), reserved + reductions, buffer_minutes)
    except (TypeError, ValueError, ZoneInfoNotFoundError):
        return None


def _reduction_minutes(rows: tuple[RowMapping, ...], physical: int) -> int:
    total = 0
    for row in rows:
        if row["reduction_minutes"] is not None:
            total += int(row["reduction_minutes"])
        else:
            raw = Decimal(physical) * Decimal(row["reduction_percent"]) / Decimal(100)
            total += int((raw / Decimal(15)).to_integral_value(rounding=ROUND_CEILING)) * 15
    return min(physical, total)


_PATTERNS = """
SELECT * FROM working_patterns
WHERE user_id=ANY(CAST(:user_ids AS uuid[])) AND valid_from<=:start
  AND (valid_until IS NULL OR :end<=valid_until)
ORDER BY user_id,valid_from DESC LIMIT 1001
"""

_EVENTS = """
SELECT event.owner_user_id user_id,event.starts_at,event.ends_at,event.all_day_start,
       event.all_day_end,event.time_zone,event.recurrence_rule,event.availability_effect,
       exceptions.exception_rows
FROM calendar_events event
LEFT JOIN LATERAL (
  SELECT jsonb_agg(jsonb_build_object(
    'occurrence_key',occurrence_key,'action',action,'replacement',replacement
  ) ORDER BY occurrence_key) AS exception_rows
  FROM calendar_event_exceptions WHERE event_id=event.event_id
) exceptions ON TRUE
WHERE event.owner_user_id=ANY(CAST(:user_ids AS uuid[])) AND event.status='active'
  AND (availability_effect IN ('partial','unavailable') OR EXISTS (
    SELECT 1 FROM calendar_event_exceptions blocking
    WHERE blocking.event_id=event.event_id AND blocking.action='change'
      AND blocking.replacement->>'availability' IN ('partial','unavailable')))
  AND ((starts_at<:end AND ends_at>:start) OR recurrence_rule IS NOT NULL OR
       (all_day_start < (timezone(time_zone,:end)::date + 1)
        AND all_day_end > timezone(time_zone,:start)::date))
ORDER BY event.owner_user_id,event.event_id LIMIT 250001
"""

_RESERVATIONS = """
SELECT user_id,coalesce(sum(reserved_minutes),0) reserved_minutes
FROM capacity_reservations
WHERE user_id=ANY(CAST(:user_ids AS uuid[])) AND state IN ('held','active')
  AND starts_at<:end AND ends_at>:start GROUP BY user_id
"""

_EXCEPTIONS = """
SELECT user_id,reduction_minutes,reduction_percent FROM capacity_exceptions
WHERE user_id=ANY(CAST(:user_ids AS uuid[])) AND starts_at<:end AND ends_at>:start
ORDER BY user_id,starts_at LIMIT 250001
"""
