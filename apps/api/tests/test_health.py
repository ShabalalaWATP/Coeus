import pytest
from httpx import AsyncClient

from coeus.api.dependencies import get_readiness_checker
from coeus.db.session import ReadinessCheckResult
from coeus.main import create_app


class ReadyChecker:
    async def check(self) -> ReadinessCheckResult:
        return ReadinessCheckResult(ready=True, detail="database reachable")


class NotReadyChecker:
    async def check(self) -> ReadinessCheckResult:
        return ReadinessCheckResult(ready=False, detail="database connectivity failed")


@pytest.mark.asyncio
async def test_liveness_returns_request_id(api_client: AsyncClient) -> None:
    response = await api_client.get("/api/v1/health/live", headers={"X-Request-ID": "req-live"})

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "req-live"
    assert response.json()["request_id"] == "req-live"
    assert response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_readiness_returns_ready_when_database_check_passes() -> None:
    app = create_app()
    app.dependency_overrides[get_readiness_checker] = lambda: ReadyChecker()

    from httpx import ASGITransport, AsyncClient

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/api/v1/health/ready", headers={"X-Request-ID": "req-ready"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready"
    assert payload["components"] == [
        {"name": "postgresql", "status": "ready", "detail": "database reachable"}
    ]


@pytest.mark.asyncio
async def test_readiness_returns_503_when_database_check_fails() -> None:
    app = create_app()
    app.dependency_overrides[get_readiness_checker] = lambda: NotReadyChecker()

    from httpx import ASGITransport, AsyncClient

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/api/v1/health/ready")

    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"
    assert response.json()["components"][0]["status"] == "not_ready"
