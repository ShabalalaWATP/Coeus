"""Unit coverage for conservative team-capacity arithmetic and authority."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any, cast
from uuid import uuid4

import pytest
from sqlalchemy.engine import Connection, RowMapping

from coeus.domain.capacity_forecast import CapacityForecast
from coeus.domain.organisation_authority import OrganisationAuthorityDenied
from coeus.domain.team_capacity_forecast import TeamCapacityForecastDenied, TeamForecastStatus
from coeus.persistence.team_capacity_forecast_postgres import (
    _authorise,
    _event_intervals,
    _person_forecast,
    _reduction_minutes,
    _team_forecast,
    _working_intervals,
)

NOW = datetime(2026, 8, 3, 8, tzinfo=UTC)


class _Result:
    def __init__(self, rows: tuple[dict[str, Any], ...] = (), scalar: Any = None) -> None:
        self.rows, self.scalar = rows, scalar

    def mappings(self) -> "_Result":
        return self

    def __iter__(self):
        return iter(self.rows)

    def scalar_one(self) -> Any:
        return self.scalar

    def first(self) -> object | None:
        return self.rows[0] if self.rows else None


class _Connection:
    def __init__(self, *results: _Result) -> None:
        self.results = list(results)

    def execute(self, *_args: object, **_kwargs: object) -> _Result:
        return self.results.pop(0)


def _pattern(**changes: object) -> RowMapping:
    value: dict[str, object] = {"time_zone": "Europe/London"}
    for day in ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"):
        value[f"{day}_minutes"] = 480
    value.update(changes)
    return cast(RowMapping, value)


def test_working_intervals_and_reductions_are_conservative() -> None:
    intervals = _working_intervals(_pattern(), NOW, NOW + timedelta(hours=10))
    total = sum(int((item.ends_at - item.starts_at).total_seconds() / 60) for item in intervals)
    assert total == 480
    with pytest.raises(ValueError, match="no capacity"):
        _working_intervals(_pattern(monday_minutes=0), NOW, NOW + timedelta(hours=10))
    connection = _Connection(
        _Result(
            rows=(
                {"reduction_minutes": 30, "reduction_percent": None},
                {"reduction_minutes": None, "reduction_percent": Decimal("12.5")},
            )
        )
    )
    reductions = _reduction_minutes(
        cast(Connection, connection), uuid4(), NOW, NOW + timedelta(days=1), 480
    )
    assert reductions == 90


def test_event_and_person_forecast_fail_closed_or_reconcile() -> None:
    with pytest.raises(ValueError, match="too large"):
        _event_intervals(
            cast(Connection, _Connection(_Result(rows=tuple({} for _ in range(501))))),
            uuid4(),
            NOW,
            NOW + timedelta(days=1),
        )
    connection = _Connection(
        _Result(rows=(_pattern(),)),
        _Result(rows=()),
        _Result(scalar=60),
        _Result(rows=()),
    )
    forecast, reserved, reductions = _person_forecast(
        cast(Connection, connection), uuid4(), NOW, NOW + timedelta(hours=10), 15
    )
    assert reserved == 60 and reductions == 0 and forecast.assignable_minutes == 405
    with pytest.raises(ValueError, match="one pattern"):
        _person_forecast(
            cast(Connection, _Connection(_Result(rows=()))),
            uuid4(),
            NOW,
            NOW + timedelta(hours=1),
            0,
        )


def test_team_status_and_authority_are_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    ready = CapacityForecast(480, 0, 0, 60, 0, 420)
    partial = _team_forecast(uuid4(), NOW, NOW + timedelta(days=1), 2, 1, [(ready, 60, 0)], 0, NOW)
    assert partial.status is TeamForecastStatus.PARTIAL
    unknown = _team_forecast(uuid4(), NOW, NOW + timedelta(days=1), 1, 1, [], 0, NOW)
    assert unknown.status is TeamForecastStatus.UNKNOWN

    monkeypatch.setattr(
        "coeus.persistence.team_capacity_forecast_postgres.validate_lineage",
        lambda *_args: None,
    )
    allowed = cast(Connection, _Connection(_Result(rows=({"ok": 1},))))
    _authorise(allowed, uuid4(), uuid4(), uuid4(), NOW)

    def deny(*_args: object) -> None:
        raise OrganisationAuthorityDenied

    monkeypatch.setattr("coeus.persistence.team_capacity_forecast_postgres.validate_lineage", deny)
    with pytest.raises(TeamCapacityForecastDenied):
        _authorise(cast(Connection, _Connection()), uuid4(), uuid4(), uuid4(), NOW)
