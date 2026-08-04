"""Shadow-only relational capacity evidence for deterministic JIOC routing."""

from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

from coeus.domain.jioc_principals import JIOC_AGENT_PRINCIPAL, JIOC_CAPACITY_GRANT_ID
from coeus.domain.jioc_routing import RoutingOperationalSnapshot
from coeus.domain.organisation import ManagementAction
from coeus.domain.organisation_authority import OrganisationAuthorityDenied
from coeus.domain.team_capacity_forecast import (
    TeamCapacityForecastIntegrityError,
    TeamForecastStatus,
)
from coeus.domain.tickets import TicketRecord
from coeus.persistence.organisation_authority_validation import transaction_time, validate_lineage
from coeus.persistence.team_capacity_forecast_postgres import forecast_team_in_transaction

RELATIONAL_CONTEXT_VERSION = "capability-catalogue-v1:relational-capacity-shadow-v1"
MAX_CANDIDATES = 32
MAX_MAPPINGS_PER_CANDIDATE = 20


class PostgresShadowRoutingOperationalContext:
    """Read minimised eligible-team forecasts without changing route authority."""

    def __init__(self, engine: Engine, *, horizon_days: int = 7) -> None:
        if not 1 <= horizon_days <= 31:
            raise ValueError("routing capacity horizon must be between 1 and 31 days")
        self._engine = engine
        self._horizon_days = horizon_days

    def snapshot(
        self, ticket: TicketRecord, candidate_team_ids: tuple[str, ...]
    ) -> RoutingOperationalSnapshot:
        del ticket
        candidates = _validated_candidates(candidate_team_ids)
        with (
            self._engine.connect().execution_options(
                isolation_level="REPEATABLE READ"
            ) as connection,
            connection.begin(),
        ):
            captured_at = transaction_time(connection)
            window_end = captured_at + timedelta(days=self._horizon_days)
            values = tuple(
                _candidate_capacity(connection, candidate, captured_at, window_end)
                for candidate in candidates
            )
        return RoutingOperationalSnapshot(RELATIONAL_CONTEXT_VERSION, captured_at, values)


def _validated_candidates(candidate_ids: tuple[str, ...]) -> tuple[str, ...]:
    if len(candidate_ids) > MAX_CANDIDATES or len(set(candidate_ids)) != len(candidate_ids):
        raise ValueError("routing candidate set is invalid")
    if any(
        not value
        or value != value.strip()
        or len(value) > 120
        or ":" in value
        or any(ord(character) < 32 for character in value)
        for value in candidate_ids
    ):
        raise ValueError("routing candidate identifier is invalid")
    return candidate_ids


def _candidate_capacity(
    connection: Connection,
    candidate_id: str,
    window_start: datetime,
    window_end: datetime,
) -> str:
    try:
        rows = tuple(
            connection.execute(
                text(_MAPPINGS),
                {"candidate_id": candidate_id, "at": window_start},
            ).mappings()
        )
        if not rows or len(rows) > MAX_MAPPINGS_PER_CANDIDATE:
            return f"{candidate_id}:unknown:0"
        forecasts = []
        for row in rows:
            unit_id = UUID(str(row["unit_id"]))
            validate_lineage(
                connection,
                JIOC_CAPACITY_GRANT_ID,
                JIOC_AGENT_PRINCIPAL,
                unit_id,
                ManagementAction.RECOMMENDATION_VIEW,
                window_start,
            )
            forecasts.append(
                forecast_team_in_transaction(
                    connection,
                    unit_id,
                    window_start,
                    window_end,
                    window_start,
                )
            )
    except (
        OrganisationAuthorityDenied,
        TeamCapacityForecastIntegrityError,
        TypeError,
        ValueError,
    ):
        return f"{candidate_id}:unknown:0"
    if any(item.status is not TeamForecastStatus.READY for item in forecasts):
        return f"{candidate_id}:unknown:0"
    assignable = sum(item.assignable_minutes for item in forecasts)
    status = "available" if assignable > 0 else "unavailable"
    return f"{candidate_id}:{status}:{assignable}"


_MAPPINGS = """
SELECT profile.unit_id
FROM team_capability_coverage coverage
JOIN team_delivery_profiles profile ON profile.profile_id=coverage.profile_id
JOIN organisation_units unit ON unit.unit_id=profile.unit_id
WHERE coverage.capability_id=:candidate_id
  AND coverage.valid_from<=:at
  AND (coverage.valid_until IS NULL OR :at<coverage.valid_until)
  AND profile.is_active AND unit.is_active
  AND unit.valid_from<=:at AND (unit.valid_until IS NULL OR :at<unit.valid_until)
ORDER BY profile.unit_id
LIMIT 21
"""
