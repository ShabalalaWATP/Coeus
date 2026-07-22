import json
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from coeus.core.config import Settings
from coeus.core.errors import AppError
from coeus.domain.outbox import OutboxEventNotFound, OutboxStatus, ReplayDisposition
from coeus.main import create_app
from coeus.services.admin_analytics import _outbox_analytics
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
    assert body["outbox"] == {
        "configured": False,
        "available": False,
        "pendingCount": 0,
        "retryingCount": 0,
        "deadLetterCount": 0,
        "oldestPendingAgeSeconds": None,
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


class _AdminOutbox:
    def __init__(self) -> None:
        self.replayed: set[UUID] = set()

    def status(self) -> OutboxStatus:
        return OutboxStatus(4, 2, 1, 90)

    def replay_dead_letter(self, event_id: UUID) -> ReplayDisposition:
        if event_id in self.replayed:
            return ReplayDisposition.ALREADY_PENDING
        self.replayed.add(event_id)
        return ReplayDisposition.REPLAYED


@pytest.mark.asyncio
async def test_admin_can_inspect_and_idempotently_replay_dead_letters_with_a_reason() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    outbox = _AdminOutbox()
    app.state.outbox_dispatcher = outbox
    event_id = uuid4()

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        csrf = (await login(client, "admin@example.test"))["csrfToken"]
        dashboard = await client.get("/api/v1/analytics/admin/platform")
        first = await client.post(
            f"/api/v1/analytics/admin/outbox/{event_id}/replay",
            headers={"X-CSRF-Token": csrf},
            json={"reason": "Synthetic recovery drill"},
        )
        second = await client.post(
            f"/api/v1/analytics/admin/outbox/{event_id}/replay",
            headers={"X-CSRF-Token": csrf},
            json={"reason": "Synthetic recovery drill"},
        )

    assert dashboard.status_code == 200
    assert dashboard.json()["outbox"] == {
        "configured": True,
        "available": True,
        "pendingCount": 4,
        "retryingCount": 2,
        "deadLetterCount": 1,
        "oldestPendingAgeSeconds": 90,
    }
    assert first.status_code == second.status_code == 200
    assert first.json() == {"eventId": str(event_id), "disposition": "replayed"}
    assert second.json() == {
        "eventId": str(event_id),
        "disposition": "already_pending",
    }
    replay_events = tuple(
        item
        for item in app.state.auth_service.audit_log.list_events()
        if item.event_type == "outbox_dead_letter_replay_authorised"
    )
    assert len(replay_events) == 2
    assert replay_events[0].metadata["event_id"] == str(event_id)
    assert replay_events[0].metadata["reason"] == "Synthetic recovery drill"


@pytest.mark.asyncio
async def test_outbox_replay_requires_configuration_permission_csrf_and_reason() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    app.state.outbox_dispatcher = _AdminOutbox()
    event_id = uuid4()

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        user_csrf = (await login(client, "user@example.test"))["csrfToken"]
        forbidden = await client.post(
            f"/api/v1/analytics/admin/outbox/{event_id}/replay",
            headers={"X-CSRF-Token": user_csrf},
            json={"reason": "Synthetic recovery drill"},
        )
        admin_csrf = (await login(client, "admin@example.test"))["csrfToken"]
        no_csrf = await client.post(
            f"/api/v1/analytics/admin/outbox/{event_id}/replay",
            json={"reason": "Synthetic recovery drill"},
        )
        no_reason = await client.post(
            f"/api/v1/analytics/admin/outbox/{event_id}/replay",
            headers={"X-CSRF-Token": admin_csrf},
            json={"reason": "   "},
        )

    assert forbidden.status_code == 403
    assert no_csrf.status_code == 403
    assert no_reason.status_code == 422
    assert app.state.outbox_dispatcher.replayed == set()


@pytest.mark.asyncio
async def test_outbox_replay_reports_when_delivery_is_not_configured() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        csrf = (await login(client, "admin@example.test"))["csrfToken"]
        response = await client.post(
            f"/api/v1/analytics/admin/outbox/{uuid4()}/replay",
            headers={"X-CSRF-Token": csrf},
            json={"reason": "Synthetic recovery drill"},
        )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "outbox_not_configured"


def test_outbox_replay_audit_failure_prevents_the_state_change(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    actor = app.state.auth_service.login("admin@example.test", "CoeusLocal1!").user
    outbox = _AdminOutbox()

    def reject_audit(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("synthetic audit failure")

    monkeypatch.setattr(app.state.auth_service.audit_log, "record", reject_audit)

    with pytest.raises(RuntimeError, match="audit failure"):
        app.state.admin_analytics_service.replay_dead_letter(
            actor,
            outbox,
            uuid4(),
            "Synthetic recovery drill",
        )

    assert outbox.replayed == set()


def test_outbox_replay_service_defends_its_permission_boundary() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    actor = app.state.auth_service.login("user@example.test", "CoeusLocal1!").user

    with pytest.raises(AppError) as denied:
        app.state.admin_analytics_service.replay_dead_letter(
            actor,
            _AdminOutbox(),
            uuid4(),
            "Synthetic recovery drill",
        )

    assert denied.value.status_code == 403


def test_outbox_replay_service_requires_a_meaningful_reason() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    actor = app.state.auth_service.login("admin@example.test", "CoeusLocal1!").user
    outbox = _AdminOutbox()

    with pytest.raises(AppError) as denied:
        app.state.admin_analytics_service.replay_dead_letter(
            actor,
            outbox,
            uuid4(),
            "   ",
        )

    assert denied.value.status_code == 422
    assert outbox.replayed == set()


@pytest.mark.asyncio
async def test_outbox_status_and_unknown_replay_fail_without_exposing_content() -> None:
    class UnavailableOutbox(_AdminOutbox):
        def status(self) -> OutboxStatus:
            raise RuntimeError("synthetic private failure detail")

        def replay_dead_letter(self, event_id: UUID) -> ReplayDisposition:
            raise OutboxEventNotFound(str(event_id))

    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    app.state.outbox_dispatcher = UnavailableOutbox()
    event_id = uuid4()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        csrf = (await login(client, "admin@example.test"))["csrfToken"]
        dashboard = await client.get("/api/v1/analytics/admin/platform")
        replay = await client.post(
            f"/api/v1/analytics/admin/outbox/{event_id}/replay",
            headers={"X-CSRF-Token": csrf},
            json={"reason": "Synthetic recovery drill"},
        )

    assert dashboard.status_code == 200
    assert dashboard.json()["outbox"] == {
        "configured": True,
        "available": False,
        "pendingCount": 0,
        "retryingCount": 0,
        "deadLetterCount": 0,
        "oldestPendingAgeSeconds": None,
    }
    assert replay.status_code == 404
    assert replay.json()["error"]["code"] == "outbox_event_not_found"
    assert "private failure detail" not in replay.text


def test_outbox_status_failure_logs_only_a_fixed_safe_event(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sentinel = "synthetic private status detail"

    class UnavailableOutbox(_AdminOutbox):
        def status(self) -> OutboxStatus:
            raise RuntimeError(sentinel)

    logger = MagicMock()
    monkeypatch.setattr("coeus.services.admin_analytics.logger", logger)

    analytics = _outbox_analytics(UnavailableOutbox())

    assert analytics.available is False
    logger.warning.assert_called_once_with("outbox_status_failed")
    assert sentinel not in repr(logger.mock_calls)
