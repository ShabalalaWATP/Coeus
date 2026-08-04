"""Fail-closed tests for relational JIOC shadow capacity evidence."""

from datetime import UTC, datetime, timedelta
from typing import Any, cast
from uuid import uuid4

import pytest
from sqlalchemy.engine import Connection

from coeus.domain.team_capacity_forecast import TeamCapacityForecast, TeamForecastStatus
from coeus.persistence.jioc_routing_context_postgres import (
    PostgresShadowRoutingOperationalContext,
    _candidate_capacity,
    _validated_candidates,
)

NOW = datetime(2026, 8, 4, 8, tzinfo=UTC)


class _Rows:
    def __init__(self, rows: tuple[dict[str, Any], ...]) -> None:
        self.rows = rows

    def mappings(self) -> "_Rows":
        return self

    def __iter__(self):
        return iter(self.rows)


class _Connection:
    def __init__(self, rows: tuple[dict[str, Any], ...]) -> None:
        self.rows = rows

    def execute(self, *_args: object, **_kwargs: object) -> _Rows:
        return _Rows(self.rows)


def _forecast(
    unit_id: object,
    minutes: int = 480,
    status: TeamForecastStatus = TeamForecastStatus.READY,
) -> TeamCapacityForecast:
    return TeamCapacityForecast(
        unit_id,
        NOW,
        NOW + timedelta(days=7),
        status,
        1,
        1,
        0,
        480,
        0,
        0,
        0,
        0,
        minutes,
        NOW,
    )


def test_candidate_identifiers_are_bounded_and_unambiguous() -> None:
    with pytest.raises(ValueError, match="horizon"):
        PostgresShadowRoutingOperationalContext(cast(Any, object()), horizon_days=0)
    assert _validated_candidates(("RFA-MARITIME",)) == ("RFA-MARITIME",)
    for values in (("same", "same"), ("bad:value",), tuple(str(i) for i in range(33))):
        with pytest.raises(ValueError, match="candidate"):
            _validated_candidates(values)


def test_candidate_capacity_is_minimised_and_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    unit_id = uuid4()
    connection = cast(Connection, _Connection(({"unit_id": unit_id},)))
    monkeypatch.setattr(
        "coeus.persistence.jioc_routing_context_postgres.validate_lineage",
        lambda *_args: None,
    )
    monkeypatch.setattr(
        "coeus.persistence.jioc_routing_context_postgres.forecast_team_in_transaction",
        lambda *_args: _forecast(unit_id),
    )
    result = _candidate_capacity(connection, "RFA-MARITIME", NOW, NOW + timedelta(days=7))
    assert result == "RFA-MARITIME:available:480"
    monkeypatch.setattr(
        "coeus.persistence.jioc_routing_context_postgres.forecast_team_in_transaction",
        lambda *_args: _forecast(unit_id, 0),
    )
    assert (
        _candidate_capacity(connection, "RFA-MARITIME", NOW, NOW + timedelta(days=7))
        == "RFA-MARITIME:unavailable:0"
    )
    monkeypatch.setattr(
        "coeus.persistence.jioc_routing_context_postgres.forecast_team_in_transaction",
        lambda *_args: _forecast(unit_id, status=TeamForecastStatus.PARTIAL),
    )
    assert (
        _candidate_capacity(connection, "RFA-MARITIME", NOW, NOW + timedelta(days=7))
        == "RFA-MARITIME:unknown:0"
    )
    missing = cast(Connection, _Connection(()))
    assert _candidate_capacity(missing, "RFA-CYBER", NOW, NOW + timedelta(days=7)) == (
        "RFA-CYBER:unknown:0"
    )

    def deny(*_args: object) -> None:
        raise ValueError("revoked")

    monkeypatch.setattr(
        "coeus.persistence.jioc_routing_context_postgres.validate_lineage",
        deny,
    )
    assert _candidate_capacity(connection, "RFA-MARITIME", NOW, NOW + timedelta(days=7)) == (
        "RFA-MARITIME:unknown:0"
    )
