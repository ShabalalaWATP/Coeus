"""Branch coverage for privacy-bounded aggregate capacity forecasts."""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any, cast
from uuid import uuid4

import pytest
from sqlalchemy.engine import Connection

from coeus.domain.capacity_forecast import CapacityForecast
from coeus.domain.team_capacity_forecast import (
    TeamCapacityForecast,
    TeamCapacityForecastDenied,
    TeamCapacityForecastIntegrityError,
    TeamForecastStatus,
)
from coeus.persistence.team_capacity_forecast_postgres import (
    PostgresTeamCapacityForecastStore,
    _authorise,
    _team_forecast,
    forecast_team_in_transaction,
)
from coeus.services.team_capacity_forecast import TeamCapacityForecastService

NOW = datetime(2026, 8, 4, 8, tzinfo=UTC)


class _Result:
    def __init__(self, rows: tuple[dict[str, Any], ...] = ()) -> None:
        self.rows = rows

    def mappings(self) -> "_Result":
        return self

    def first(self) -> dict[str, Any] | None:
        return self.rows[0] if self.rows else None

    def __iter__(self) -> Iterator[dict[str, Any]]:
        return iter(self.rows)


class _Connection:
    def __init__(self, *results: _Result) -> None:
        self.results = list(results)

    def execute(self, *_args: object, **_kwargs: object) -> _Result:
        return self.results.pop(0)


def _forecast(**changes: object) -> TeamCapacityForecast:
    values: dict[str, object] = {
        "unit_id": uuid4(),
        "window_start": NOW,
        "window_end": NOW + timedelta(days=1),
        "status": TeamForecastStatus.READY,
        "people_considered": 1,
        "people_included": 1,
        "people_unknown": 0,
        "physical_minutes": 480,
        "unavailable_minutes": 0,
        "reservation_minutes": 0,
        "capacity_reduction_minutes": 0,
        "policy_buffer_minutes": 0,
        "assignable_minutes": 480,
        "as_of": NOW,
    }
    values.update(changes)
    return TeamCapacityForecast(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("changes", "message"),
    (
        ({"window_start": NOW.replace(tzinfo=None)}, "timezone-aware"),
        ({"window_end": NOW}, "end must follow"),
        ({"people_included": -1, "people_unknown": 2}, "cannot be negative"),
        ({"assignable_minutes": 1}, "15-minute"),
    ),
)
def test_team_forecast_domain_remaining_validation_branches(
    changes: dict[str, object], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        _forecast(**changes)


class _ForecastStore:
    def __init__(self, result: TeamCapacityForecast) -> None:
        self.result = result
        self.call: tuple[object, ...] | None = None

    def forecast(self, *args: object) -> TeamCapacityForecast:
        self.call = args
        return self.result


def test_team_forecast_service_validates_window_and_delegates() -> None:
    result = _forecast()
    store = _ForecastStore(result)
    service = TeamCapacityForecastService(store)
    actor, unit, grant = uuid4(), uuid4(), uuid4()
    with pytest.raises(ValueError, match="timezone-aware"):
        service.forecast(actor, unit, grant, NOW.replace(tzinfo=None), NOW)
    for end in (NOW, NOW + timedelta(days=32)):
        with pytest.raises(ValueError, match="no longer than 31 days"):
            service.forecast(actor, unit, grant, NOW, end)
    assert service.forecast(actor, unit, grant, NOW, NOW + timedelta(days=1)) is result
    assert store.call == (actor, unit, grant, NOW, NOW + timedelta(days=1))


def test_team_forecast_persistence_rejects_invalid_buffer_and_cohort() -> None:
    with pytest.raises(ValueError, match="15-minute"):
        PostgresTeamCapacityForecastStore(cast(Any, object()), policy_buffer_minutes=1)
    rows = tuple({"user_id": uuid4()} for _ in range(101))
    with pytest.raises(TeamCapacityForecastIntegrityError, match="too large"):
        forecast_team_in_transaction(
            cast(Connection, _Connection(_Result(rows))),
            uuid4(),
            NOW,
            NOW + timedelta(days=1),
            NOW,
        )


def test_team_forecast_counts_ineligible_and_failed_people(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first, second = uuid4(), uuid4()
    rows = (
        {
            "user_id": first,
            "account_eligible": False,
            "covering_count": 1,
            "covers_window": True,
        },
        {
            "user_id": second,
            "account_eligible": True,
            "covering_count": 1,
            "covers_window": True,
        },
    )
    monkeypatch.setattr(
        "coeus.persistence.team_capacity_forecast_postgres._person_forecast",
        lambda *_args: (_ for _ in ()).throw(ValueError("synthetic bad evidence")),
    )
    result = forecast_team_in_transaction(
        cast(Connection, _Connection(_Result(rows))),
        uuid4(),
        NOW,
        NOW + timedelta(days=1),
        NOW,
    )
    assert result.status is TeamForecastStatus.UNKNOWN
    assert result.people_unknown == 2


def test_team_forecast_authority_rejects_inactive_delivery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "coeus.persistence.team_capacity_forecast_postgres.validate_lineage", lambda *_args: None
    )
    with pytest.raises(TeamCapacityForecastDenied):
        _authorise(cast(Connection, _Connection(_Result())), uuid4(), uuid4(), uuid4(), NOW)


def test_ready_team_status_branch() -> None:
    forecast = CapacityForecast(480, 0, 0, 0, 0, 480)
    result = _team_forecast(uuid4(), NOW, NOW + timedelta(days=1), 1, 0, [(forecast, 0, 0)], 0, NOW)
    assert result.status is TeamForecastStatus.READY
