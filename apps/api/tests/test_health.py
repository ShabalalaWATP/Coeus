from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException, Request
from httpx import AsyncClient

from coeus.api.dependencies import get_readiness_checker
from coeus.api.routes.health import _require_metrics_access
from coeus.core.config import Settings
from coeus.db.session import ReadinessCheckResult
from coeus.domain.outbox import OutboxStatus
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
async def test_metrics_exposes_low_cardinality_admission_counters() -> None:
    app = create_app()
    app.state.admission_metrics.record("search", "denied_principal")
    with app.state.provider_admission.reserve(uuid4()):
        pass
    from httpx import ASGITransport

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.get("/api/v1/metrics")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert 'coeus_admission_total{resource="search",outcome="denied_principal"} 1' in response.text
    assert "principal_id" not in response.text
    assert 'coeus_admission_total{resource="provider",outcome="admitted"} 1' in response.text
    assert "coeus_outbox_configured 0" in response.text
    assert "coeus_outbox_available 0" in response.text
    assert "coeus_outbox_pending_messages 0" in response.text


@pytest.mark.asyncio
async def test_metrics_requires_and_accepts_the_configured_bearer_token() -> None:
    token = "m" * 32
    app = create_app(Settings(environment="test", metrics_bearer_token=token))
    from httpx import ASGITransport

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        missing = await client.get("/api/v1/metrics")
        invalid = await client.get(
            "/api/v1/metrics", headers={"Authorization": "Bearer invalid-token"}
        )
        wrong_scheme = await client.get(
            "/api/v1/metrics", headers={"Authorization": f"Basic {token}"}
        )
        valid = await client.get("/api/v1/metrics", headers={"Authorization": f"Bearer {token}"})

    assert missing.status_code == invalid.status_code == wrong_scheme.status_code == 401
    assert missing.headers["www-authenticate"] == "Bearer"
    assert token not in missing.text
    assert token not in invalid.text
    assert token not in wrong_scheme.text
    assert valid.status_code == 200
    assert "coeus_admission_total" in valid.text


def test_metrics_access_fails_closed_outside_local_and_test() -> None:
    request = Request({"type": "http", "headers": []})

    with pytest.raises(HTTPException) as denied:
        _require_metrics_access(request, Settings(environment="dev"))

    assert denied.value.status_code == 401
    assert denied.value.headers == {"WWW-Authenticate": "Bearer"}


@pytest.mark.asyncio
async def test_metrics_exposes_payload_free_outbox_operational_gauges() -> None:
    class Outbox:
        def metrics_status(self) -> OutboxStatus:
            return OutboxStatus(7, 3, 2, 120)

        def status(self) -> OutboxStatus:
            raise AssertionError("metrics must not query live outbox status")

    app = create_app()
    app.state.outbox_dispatcher = Outbox()
    from httpx import ASGITransport

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.get("/api/v1/metrics")

    assert response.status_code == 200
    assert "coeus_outbox_configured 1" in response.text
    assert "coeus_outbox_available 1" in response.text
    assert "coeus_outbox_pending_messages 7" in response.text
    assert "coeus_outbox_retrying_messages 3" in response.text
    assert "coeus_outbox_dead_letter_messages 2" in response.text
    assert "coeus_outbox_oldest_pending_age_seconds 120" in response.text
    assert "payload" not in response.text


@pytest.mark.asyncio
async def test_metrics_degrade_safely_without_querying_live_outbox_status() -> None:
    class UnavailableOutbox:
        def metrics_status(self) -> None:
            return None

        def status(self) -> OutboxStatus:
            raise AssertionError("metrics must not query live outbox status")

    app = create_app()
    app.state.outbox_dispatcher = UnavailableOutbox()
    from httpx import ASGITransport

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.get("/api/v1/metrics")

    assert response.status_code == 200
    assert "coeus_outbox_configured 1" in response.text
    assert "coeus_outbox_available 0" in response.text
    assert "coeus_outbox_dead_letter_messages 0" in response.text


@pytest.mark.asyncio
async def test_metrics_snapshot_failure_logs_only_a_fixed_safe_event(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sentinel = "synthetic private metrics detail"

    class UnavailableOutbox:
        def metrics_status(self) -> None:
            raise RuntimeError(sentinel)

    logger = MagicMock()
    monkeypatch.setattr("coeus.api.routes.health.logger", logger)
    app = create_app()
    app.state.outbox_dispatcher = UnavailableOutbox()
    from httpx import ASGITransport

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.get("/api/v1/metrics")

    assert response.status_code == 200
    assert "coeus_outbox_available 0" in response.text
    logger.warning.assert_called_once_with("outbox_metrics_snapshot_failed")
    assert sentinel not in repr(logger.mock_calls)


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
