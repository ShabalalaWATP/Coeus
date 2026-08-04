"""Exact-authority advisory team capacity forecasts from canonical evidence."""

from datetime import UTC, datetime, time, timedelta
from decimal import ROUND_CEILING, Decimal
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine, RowMapping

from coeus.application.ports.team_capacity_forecast import TeamCapacityForecastStore
from coeus.domain.capacity_forecast import CapacityForecast, CapacityInterval, forecast_capacity
from coeus.domain.organisation import ManagementAction
from coeus.domain.organisation_authority import OrganisationAuthorityDenied
from coeus.domain.team_capacity_forecast import (
    TeamCapacityForecast,
    TeamCapacityForecastDenied,
    TeamCapacityForecastIntegrityError,
    TeamForecastStatus,
)
from coeus.persistence.calendar_capacity_expansion import capacity_intervals
from coeus.persistence.capacity_reservation_sql import DAYS
from coeus.persistence.identity_account_projection import active_analyst_role
from coeus.persistence.organisation_authority_validation import transaction_time, validate_lineage


class PostgresTeamCapacityForecastStore(TeamCapacityForecastStore):
    def __init__(self, engine: Engine, *, policy_buffer_minutes: int = 0) -> None:
        if policy_buffer_minutes < 0 or policy_buffer_minutes % 15:
            raise ValueError("capacity policy buffer must use 15-minute increments")
        self._engine = engine
        self._policy_buffer_minutes = policy_buffer_minutes

    def forecast(
        self,
        actor_user_id: UUID,
        unit_id: UUID,
        authorising_grant_id: UUID,
        window_start: datetime,
        window_end: datetime,
    ) -> TeamCapacityForecast:
        with (
            self._engine.connect().execution_options(
                isolation_level="REPEATABLE READ"
            ) as connection,
            connection.begin(),
        ):
            as_of = transaction_time(connection)
            _authorise(connection, actor_user_id, unit_id, authorising_grant_id, as_of)
            return forecast_team_in_transaction(
                connection,
                unit_id,
                window_start,
                window_end,
                as_of,
                self._policy_buffer_minutes,
            )


def forecast_team_in_transaction(
    connection: Connection,
    unit_id: UUID,
    window_start: datetime,
    window_end: datetime,
    as_of: datetime,
    policy_buffer_minutes: int = 0,
) -> TeamCapacityForecast:
    """Build one aggregate from the caller's already-authorised snapshot."""
    rows = tuple(
        connection.execute(
            text(_MEMBERS),
            {
                "unit_id": unit_id,
                "start": window_start,
                "end": window_end,
                "analyst_role": active_analyst_role(),
            },
        ).mappings()
    )
    if len(rows) > 100:
        raise TeamCapacityForecastIntegrityError("team forecast cohort is too large")
    included: list[tuple[CapacityForecast, int, int]] = []
    unknown = 0
    for row in rows:
        user_id = UUID(str(row["user_id"]))
        if (
            not bool(row["account_eligible"])
            or int(row["covering_count"]) != 1
            or not bool(row["covers_window"])
        ):
            unknown += 1
            continue
        try:
            included.append(
                _person_forecast(
                    connection,
                    user_id,
                    window_start,
                    window_end,
                    policy_buffer_minutes,
                )
            )
        except (TypeError, ValueError, ZoneInfoNotFoundError):
            unknown += 1
    return _team_forecast(
        unit_id,
        window_start,
        window_end,
        len(rows),
        unknown,
        included,
        policy_buffer_minutes,
        as_of,
    )


def _authorise(
    connection: Connection,
    actor_id: UUID,
    unit_id: UUID,
    grant_id: UUID,
    at: datetime,
) -> None:
    try:
        validate_lineage(connection, grant_id, actor_id, unit_id, ManagementAction.TASK_ASSIGN, at)
        active_delivery = connection.execute(
            text(
                "SELECT 1 FROM organisation_units unit "
                "JOIN team_delivery_profiles profile ON profile.unit_id=unit.unit_id "
                "WHERE unit.unit_id=:unit_id AND unit.is_active AND profile.is_active "
                "AND unit.valid_from<=:at AND (unit.valid_until IS NULL OR :at<unit.valid_until)"
            ),
            {"unit_id": unit_id, "at": at},
        ).first()
        if active_delivery is None:
            raise OrganisationAuthorityDenied
    except OrganisationAuthorityDenied as exc:
        raise TeamCapacityForecastDenied from exc


def _person_forecast(
    connection: Connection,
    user_id: UUID,
    start: datetime,
    end: datetime,
    buffer_minutes: int,
) -> tuple[CapacityForecast, int, int]:
    patterns = tuple(
        connection.execute(
            text(_PATTERN), {"user_id": user_id, "start": start, "end": end}
        ).mappings()
    )
    if len(patterns) != 1:
        raise ValueError("one pattern must cover the interval")
    working = _working_intervals(patterns[0], start, end)
    events = _event_intervals(connection, user_id, start, end)
    physical = forecast_capacity(working, events, (), 0, 0).physical_minutes
    reserved = int(
        connection.execute(
            text(_RESERVED), {"user_id": user_id, "start": start, "end": end}
        ).scalar_one()
        or 0
    )
    reductions = _reduction_minutes(connection, user_id, start, end, physical)
    forecast = forecast_capacity(working, events, (), reserved + reductions, buffer_minutes)
    return forecast, reserved, reductions


def _working_intervals(
    pattern: RowMapping, starts_at: datetime, ends_at: datetime
) -> tuple[CapacityInterval, ...]:
    zone = ZoneInfo(str(pattern["time_zone"]))
    local_start, local_end = starts_at.astimezone(zone), ends_at.astimezone(zone)
    minutes = tuple(int(pattern[f"{day}_minutes"]) for day in DAYS)
    intervals: list[CapacityInterval] = []
    current = local_start.date()
    while current <= local_end.date():
        shift_start = datetime.combine(current, time(9), zone)
        shift_end = shift_start + timedelta(minutes=minutes[current.weekday()])
        bounded_start = max(starts_at, shift_start.astimezone(UTC))
        bounded_end = min(ends_at, shift_end.astimezone(UTC))
        if bounded_start < bounded_end:
            intervals.append(CapacityInterval(bounded_start, bounded_end))
        current += timedelta(days=1)
    if not intervals:
        raise ValueError("pattern has no capacity")
    return tuple(intervals)


def _event_intervals(
    connection: Connection, user_id: UUID, start: datetime, end: datetime
) -> tuple[CapacityInterval, ...]:
    rows = tuple(
        connection.execute(
            text(_CALENDAR), {"user_id": user_id, "start": start, "end": end}
        ).mappings()
    )
    if len(rows) > 500:
        raise ValueError("calendar evidence is too large")
    values: list[CapacityInterval] = []
    for row in rows:
        values.extend(capacity_intervals(dict(row), start, end))
    return tuple(values)


def _reduction_minutes(
    connection: Connection, user_id: UUID, start: datetime, end: datetime, physical: int
) -> int:
    rows = connection.execute(
        text(_EXCEPTIONS), {"user_id": user_id, "start": start, "end": end}
    ).mappings()
    total = 0
    for row in rows:
        if row["reduction_minutes"] is not None:
            total += int(row["reduction_minutes"])
        else:
            raw = Decimal(physical) * Decimal(row["reduction_percent"]) / Decimal(100)
            total += int((raw / Decimal(15)).to_integral_value(rounding=ROUND_CEILING)) * 15
    return min(physical, total)


def _team_forecast(
    unit_id: UUID,
    start: datetime,
    end: datetime,
    considered: int,
    unknown: int,
    values: list[tuple[CapacityForecast, int, int]],
    buffer_per_person: int,
    as_of: datetime,
) -> TeamCapacityForecast:
    status = (
        TeamForecastStatus.UNKNOWN
        if not values
        else TeamForecastStatus.PARTIAL
        if unknown
        else TeamForecastStatus.READY
    )
    return TeamCapacityForecast(
        unit_id,
        start,
        end,
        status,
        considered,
        len(values),
        unknown,
        sum(item[0].physical_minutes for item in values),
        sum(item[0].unavailable_minutes for item in values),
        sum(item[1] for item in values),
        sum(item[2] for item in values),
        buffer_per_person * len(values),
        sum(item[0].assignable_minutes for item in values),
        as_of,
    )


_MEMBERS = """
SELECT member.user_id,
       account.user_id IS NOT NULL AND account.is_active
         AND :analyst_role=ANY(account.roles) AS account_eligible,
       member.valid_until IS NULL OR :end<=member.valid_until AS covers_window,
       (SELECT count(*) FROM team_memberships covering
        WHERE covering.user_id=member.user_id AND covering.state='active'
          AND covering.valid_from<=:start
          AND (covering.valid_until IS NULL OR :start<covering.valid_until)) AS covering_count
FROM team_memberships member
LEFT JOIN identity_account_projection account ON account.user_id=member.user_id
WHERE member.unit_id=:unit_id AND member.state='active' AND member.assignment_eligible
  AND member.valid_from<=:start AND (member.valid_until IS NULL OR :start<member.valid_until)
ORDER BY member.user_id LIMIT 101
"""

_PATTERN = """
SELECT * FROM working_patterns WHERE user_id=:user_id AND valid_from<=:start
  AND (valid_until IS NULL OR :end<=valid_until) LIMIT 2
"""

_CALENDAR = """
SELECT event.starts_at,event.ends_at,event.all_day_start,event.all_day_end,
       event.time_zone,event.recurrence_rule,event.availability_effect,
       exceptions.exception_rows
FROM calendar_events event
LEFT JOIN LATERAL (
  SELECT jsonb_agg(jsonb_build_object(
    'occurrence_key',occurrence_key,'action',action,'replacement',replacement
  ) ORDER BY occurrence_key) AS exception_rows
  FROM calendar_event_exceptions WHERE event_id=event.event_id
) exceptions ON TRUE
WHERE event.owner_user_id=:user_id AND event.status='active'
  AND (
    availability_effect IN ('partial','unavailable')
    OR EXISTS (
      SELECT 1 FROM calendar_event_exceptions blocking
      WHERE blocking.event_id=event.event_id AND blocking.action='change'
        AND blocking.replacement->>'availability' IN ('partial','unavailable')
    )
  )
  AND ((starts_at<:end AND ends_at>:start) OR recurrence_rule IS NOT NULL OR
       (all_day_start < (timezone(time_zone,:end)::date + 1)
        AND all_day_end > timezone(time_zone,:start)::date))
ORDER BY event.event_id LIMIT 501
"""

_RESERVED = """
SELECT coalesce(sum(reserved_minutes),0) FROM capacity_reservations
WHERE user_id=:user_id AND state IN ('held','active') AND starts_at<:end AND ends_at>:start
"""

_EXCEPTIONS = """
SELECT reduction_minutes,reduction_percent FROM capacity_exceptions
WHERE user_id=:user_id AND starts_at<:end AND ends_at>:start
"""
