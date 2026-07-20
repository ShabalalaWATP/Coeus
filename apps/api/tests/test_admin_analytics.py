import json

import pytest
from httpx import ASGITransport, AsyncClient

from coeus.core.config import Settings
from coeus.main import create_app
from coeus.services.audit import AuditLog
from rfi_search_helpers import login


@pytest.mark.asyncio
async def test_admin_analytics_reports_only_aggregate_platform_signals() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    audit = app.state.auth_service.audit_log
    audit.record("ticket_chat_message_received", "synthetic-user")
    audit.record("rfi_search_completed", "synthetic-user")
    audit.record("voice_session_started", "synthetic-user", {"model": "not-returned"})
    audit.record("login_failure", None, {"reason": "not-returned"})
    audit.record("ai_model_changed", "synthetic-admin", {"ticket_id": "not-returned"})
    app.state.admission_metrics.record("provider", "admitted")
    app.state.admission_metrics.record("provider", "denied_deployment")

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        await login(client, "admin@example.test")
        response = await client.get("/api/v1/analytics/admin/platform")

    assert response.status_code == 200
    body = response.json()
    assert body["users"]["total"] >= body["users"]["active"] >= 1
    assert body["users"]["disabled"] >= 1
    assert body["users"]["roleCounts"]
    assert body["assistant"]["chatTurns30d"] == 1
    assert body["search"]["searchRuns30d"] == 1
    assert body["voice"]["sessionsStarted30d"] == 1
    assert body["audit"]["loginFailures30d"] == 1
    assert body["audit"]["configurationChanges30d"] == 1
    assert body["process"] == {
        "remoteRequestsAdmitted": 1,
        "remoteRequestsDenied": 1,
    }
    serialised = json.dumps(body)
    for forbidden in (
        "productId",
        "ticketId",
        "reference",
        "title",
        "query",
        "username",
        "actorUserId",
        "not-returned",
    ):
        assert forbidden not in serialised


@pytest.mark.asyncio
async def test_admin_analytics_exposes_bounded_audit_coverage_and_permission() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    bounded = AuditLog(max_events=2)
    bounded.record("login_success", "same-user")
    bounded.record("login_success", "same-user")
    app.state.admin_analytics_service._audit_log = bounded

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        await login(client, "admin@example.test")
        allowed = await client.get("/api/v1/analytics/admin/platform")
        await login(client, "user@example.test")
        forbidden = await client.get("/api/v1/analytics/admin/platform")

    assert allowed.status_code == 200
    assert allowed.json()["users"]["activeUsers30d"] == 1
    assert allowed.json()["audit"]["retainedEvents"] == 2
    assert allowed.json()["audit"]["retentionLimitReached"] is True
    assert allowed.json()["audit"]["coverageStartsAt"] is not None
    assert forbidden.status_code == 403


@pytest.mark.asyncio
async def test_legacy_admin_analytics_is_empty_and_permission_checked() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        await login(client, "admin@example.test")
        response = await client.get("/api/v1/analytics/admin")

    assert response.status_code == 200
    assert response.json()["metrics"]["totalTickets"] == 0
    assert response.json()["productReuse"] == []
    assert response.json()["trends"] == []
