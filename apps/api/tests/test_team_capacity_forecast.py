"""Advisory team capacity forecast service and HTTP contracts."""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from coeus.api.organisation_dependencies import get_team_capacity_forecast
from coeus.core.config import Settings
from coeus.domain.team_capacity_forecast import (
    TeamCapacityForecast,
    TeamCapacityForecastDenied,
    TeamCapacityForecastIntegrityError,
    TeamForecastStatus,
)
from coeus.main import create_app
from rfi_search_helpers import login


class _ForecastService:
    def __init__(self, result: TeamCapacityForecast | Exception) -> None:
        self.result = result
        self.call: tuple[UUID, UUID, UUID, datetime, datetime] | None = None

    def forecast(
        self,
        actor_id: UUID,
        unit_id: UUID,
        grant_id: UUID,
        start: datetime,
        end: datetime,
    ) -> TeamCapacityForecast:
        self.call = (actor_id, unit_id, grant_id, start, end)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def _forecast(unit_id: UUID, start: datetime, end: datetime) -> TeamCapacityForecast:
    return TeamCapacityForecast(
        unit_id,
        start,
        end,
        TeamForecastStatus.PARTIAL,
        4,
        3,
        1,
        7_200,
        480,
        240,
        120,
        0,
        6_360,
        datetime(2026, 8, 3, 12, tzinfo=UTC),
    )


def _url_time(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def test_forecast_domain_rejects_unreconciled_counts() -> None:
    now = datetime(2026, 8, 3, tzinfo=UTC)
    with pytest.raises(ValueError, match="counts must reconcile"):
        TeamCapacityForecast(
            uuid4(),
            now,
            now + timedelta(days=1),
            TeamForecastStatus.READY,
            2,
            1,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            now,
        )


@pytest.mark.asyncio
async def test_forecast_http_is_actor_scoped_and_bounded() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    unit_id, grant_id = uuid4(), uuid4()
    start = datetime(2026, 8, 4, tzinfo=UTC)
    end = start + timedelta(days=5)
    service = _ForecastService(_forecast(unit_id, start, end))
    app.dependency_overrides[get_team_capacity_forecast] = lambda: service
    path = (
        f"/api/v1/organisation/workspaces/{unit_id}/capacity"
        f"?authorisingGrantId={grant_id}&windowStart={_url_time(start)}"
        f"&windowEnd={_url_time(end)}"
    )
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        assert (await client.get(path)).status_code == 401
        await login(client, "rfa.team@example.test")
        response = await client.get(path)
    assert response.status_code == 200
    assert response.json()["status"] == "partial"
    assert response.json()["assignableMinutes"] == 6_360
    assert "people" not in response.json() or "peopleIncluded" in response.json()
    actor = app.state.access_services.repository.get_user_by_username("rfa.team@example.test")
    assert actor is not None and service.call == (actor.user_id, unit_id, grant_id, start, end)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error", "status", "code"),
    (
        (TeamCapacityForecastDenied(), 404, "team_workspace_not_found"),
        (ValueError("wide"), 422, "invalid_capacity_window"),
        (
            TeamCapacityForecastIntegrityError("bad evidence"),
            503,
            "capacity_forecast_unavailable",
        ),
    ),
)
async def test_forecast_http_has_generic_failures(error: Exception, status: int, code: str) -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    app.dependency_overrides[get_team_capacity_forecast] = lambda: _ForecastService(error)
    now = datetime(2026, 8, 3, tzinfo=UTC)
    path = (
        f"/api/v1/organisation/workspaces/{uuid4()}/capacity"
        f"?authorisingGrantId={uuid4()}&windowStart={_url_time(now)}"
        f"&windowEnd={_url_time(now + timedelta(days=1))}"
    )
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        await login(client, "rfa.team@example.test")
        response = await client.get(path)
    assert response.status_code == status
    assert response.json()["error"]["code"] == code
