from dataclasses import replace
from uuid import UUID

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient, Response

from coeus.api.dependencies import get_search_admission
from coeus.core.config import Settings
from coeus.domain.enums import TicketState
from coeus.main import create_app
from coeus.services.resource_admission import LocalResourceAdmissionController
from rfi_search_helpers import login, submitted_ticket


@pytest.mark.asyncio
async def test_reject_all_requires_feedback_then_supports_refined_search() -> None:
    app = create_app(
        Settings(
            environment="test",
            argon2_memory_cost=8_192,
            automatic_request_discovery_enabled=False,
            active_work_offers_enabled=False,
        )
    )
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        user = await login(client, "user@example.test")
        token = str(user["csrfToken"])
        ticket_id = await submitted_ticket(client, token)
        run = await client.post(
            f"/api/v1/rfi-search/{ticket_id}/run",
            headers={"X-CSRF-Token": token},
        )
        _make_latest_search_complete(app, ticket_id)
        rejected = await _reject_all(client, ticket_id, token, run)
        detail = await client.get(f"/api/v1/tickets/{ticket_id}")
        premature_consent = await client.post(
            f"/api/v1/tickets/{ticket_id}/no-match-consent",
            headers={"X-CSRF-Token": token},
            json={"taskAsNewRequest": True},
        )
        blank = await client.post(
            f"/api/v1/rfi-search/{ticket_id}/feedback",
            headers={"X-CSRF-Token": token},
            json={"feedback": "   "},
        )
        missing_csrf = await client.post(
            f"/api/v1/rfi-search/{ticket_id}/feedback",
            json={"feedback": "This must not be accepted without CSRF."},
        )
        too_long = await client.post(
            f"/api/v1/rfi-search/{ticket_id}/feedback",
            headers={"X-CSRF-Token": token},
            json={"feedback": "x" * 1_001},
        )
        feedback = await client.post(
            f"/api/v1/rfi-search/{ticket_id}/feedback",
            headers={"X-CSRF-Token": token},
            json={"feedback": "The reports were too old and did not cover Donetsk."},
        )
        denied_admission = LocalResourceAdmissionController(
            max_concurrent=0, max_concurrent_per_principal=1, max_units=0
        )
        app.dependency_overrides[get_search_admission] = lambda: denied_admission
        capacity_denied = await client.post(
            f"/api/v1/rfi-search/{ticket_id}/refine", headers={"X-CSRF-Token": token}
        )
        after_denial = await client.get(f"/api/v1/tickets/{ticket_id}")
        app.dependency_overrides.pop(get_search_admission)
        refined = await client.post(
            f"/api/v1/rfi-search/{ticket_id}/refine",
            headers={"X-CSRF-Token": token},
        )

    assert rejected.json()["ticketState"] == "NEW_TASKING_CONSENT"
    assert detail.json()["conversationStatus"] == "open"
    assert detail.json()["messages"][-1]["body"].startswith("Thanks for reviewing")
    assert premature_consent.status_code == 409
    assert premature_consent.json()["error"]["code"] == "rfi_search_feedback_required"
    assert blank.status_code == 422
    assert missing_csrf.status_code == 403
    assert too_long.status_code == 422
    assert feedback.status_code == 200
    assert feedback.json()["conversationStatus"] == "closed"
    assert feedback.json()["messages"][-2]["body"] == (
        "The reports were too old and did not cover Donetsk."
    )
    assert capacity_denied.status_code == 429
    assert after_denial.json()["state"] == "NEW_TASKING_CONSENT"
    assert refined.status_code == 200
    assert "customer refinement: The reports were too old" in refined.json()["metrics"]["query"]


@pytest.mark.asyncio
async def test_feedback_is_owner_only_and_latest_round_gates_consent() -> None:
    app = create_app(
        Settings(
            environment="test",
            argon2_memory_cost=8_192,
            automatic_request_discovery_enabled=False,
            active_work_offers_enabled=False,
        )
    )
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        user = await login(client, "user@example.test")
        token = str(user["csrfToken"])
        ticket_id = await submitted_ticket(client, token)
        run = await client.post(
            f"/api/v1/rfi-search/{ticket_id}/run",
            headers={"X-CSRF-Token": token},
        )
        _make_latest_search_complete(app, ticket_id)
        await _reject_all(client, ticket_id, token, run)
        admin = await login(client, "admin@example.test")
        denied = await client.post(
            f"/api/v1/rfi-search/{ticket_id}/feedback",
            headers={"X-CSRF-Token": str(admin["csrfToken"])},
            json={"feedback": "This should not be accepted."},
        )
        denied_refine = await client.post(
            f"/api/v1/rfi-search/{ticket_id}/refine",
            headers={"X-CSRF-Token": str(admin["csrfToken"])},
        )
        user = await login(client, "user@example.test")
        token = str(user["csrfToken"])
        recorded = await client.post(
            f"/api/v1/rfi-search/{ticket_id}/feedback",
            headers={"X-CSRF-Token": token},
            json={"feedback": "Need more recent reporting."},
        )
        refined = await client.post(
            f"/api/v1/rfi-search/{ticket_id}/refine",
            headers={"X-CSRF-Token": token},
        )
        _make_latest_search_complete(app, ticket_id)
        rejected_again = await _reject_all(client, ticket_id, token, refined)
        stale_feedback_consent = await client.post(
            f"/api/v1/tickets/{ticket_id}/no-match-consent",
            headers={"X-CSRF-Token": token},
            json={"taskAsNewRequest": False},
        )

    assert denied.status_code == 404
    assert denied_refine.status_code == 404
    assert recorded.status_code == 200
    assert rejected_again.json()["ticketState"] == "NEW_TASKING_CONSENT"
    assert stale_feedback_consent.status_code == 409
    assert stale_feedback_consent.json()["error"]["code"] == "rfi_search_feedback_required"


@pytest.mark.asyncio
async def test_feedback_cannot_be_replayed_for_another_refined_search() -> None:
    app = create_app(
        Settings(
            environment="test",
            argon2_memory_cost=8_192,
            automatic_request_discovery_enabled=False,
            active_work_offers_enabled=False,
        )
    )
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        user = await login(client, "user@example.test")
        token = str(user["csrfToken"])
        ticket_id = await submitted_ticket(client, token)
        run = await client.post(
            f"/api/v1/rfi-search/{ticket_id}/run", headers={"X-CSRF-Token": token}
        )
        _make_latest_search_partial(app, ticket_id)
        await _reject_all(client, ticket_id, token, run)
        await client.post(
            f"/api/v1/rfi-search/{ticket_id}/feedback",
            headers={"X-CSRF-Token": token},
            json={"feedback": "Need more recent reporting."},
        )
        generic_retry = await client.post(
            f"/api/v1/rfi-search/{ticket_id}/run", headers={"X-CSRF-Token": token}
        )
        refined = await client.post(
            f"/api/v1/rfi-search/{ticket_id}/refine", headers={"X-CSRF-Token": token}
        )
        _force_refined_no_match(app, ticket_id)
        replay = await client.post(
            f"/api/v1/rfi-search/{ticket_id}/refine", headers={"X-CSRF-Token": token}
        )
        consent = await client.post(
            f"/api/v1/tickets/{ticket_id}/no-match-consent",
            headers={"X-CSRF-Token": token},
            json={"taskAsNewRequest": True},
        )

    assert refined.status_code == 200
    assert generic_retry.json()["error"]["code"] == "rfi_refine_required"
    assert replay.status_code == 409
    assert replay.json()["error"]["code"] == "rfi_search_feedback_required"
    assert consent.status_code == 200


@pytest.mark.asyncio
async def test_refined_search_failure_becomes_retryable_incomplete(
    monkeypatch, caplog: pytest.LogCaptureFixture
) -> None:
    app = create_app(
        Settings(
            environment="test",
            argon2_memory_cost=8_192,
            automatic_request_discovery_enabled=False,
            active_work_offers_enabled=False,
        )
    )
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        user = await login(client, "user@example.test")
        token = str(user["csrfToken"])
        ticket_id = await submitted_ticket(client, token)
        run = await client.post(
            f"/api/v1/rfi-search/{ticket_id}/run", headers={"X-CSRF-Token": token}
        )
        _make_latest_search_complete(app, ticket_id)
        await _reject_all(client, ticket_id, token, run)
        await client.post(
            f"/api/v1/rfi-search/{ticket_id}/feedback",
            headers={"X-CSRF-Token": token},
            json={"feedback": "Need more recent reporting."},
        )

        def fail_search(*_args, **_kwargs):  # type: ignore[no-untyped-def]
            raise RuntimeError("synthetic retrieval failure with sensitive detail")

        monkeypatch.setattr(app.state.rfi_search_service._store_search, "search", fail_search)
        failed = await client.post(
            f"/api/v1/rfi-search/{ticket_id}/refine", headers={"X-CSRF-Token": token}
        )

    assert failed.status_code == 200
    assert failed.json()["ticketState"] == "RFI_SEARCH_INCOMPLETE"
    assert failed.json()["metrics"]["degradedReason"] == "search_failed"
    assert "sensitive" not in failed.text
    assert "sensitive detail" not in caplog.text


@pytest.mark.asyncio
async def test_partial_reject_all_still_requires_feedback_after_retry_no_match() -> None:
    app = create_app(
        Settings(
            environment="test",
            argon2_memory_cost=8_192,
            automatic_request_discovery_enabled=False,
            active_work_offers_enabled=False,
        )
    )
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        user = await login(client, "user@example.test")
        token = str(user["csrfToken"])
        ticket_id = await submitted_ticket(client, token)
        run = await client.post(
            f"/api/v1/rfi-search/{ticket_id}/run", headers={"X-CSRF-Token": token}
        )
        _make_latest_search_partial(app, ticket_id)
        rejected = await _reject_all(client, ticket_id, token, run)
        pending_retry = await client.post(
            f"/api/v1/rfi-search/{ticket_id}/run", headers={"X-CSRF-Token": token}
        )
        _force_refined_no_match(app, ticket_id)
        detail = await client.get(f"/api/v1/tickets/{ticket_id}")
        consent = await client.post(
            f"/api/v1/tickets/{ticket_id}/no-match-consent",
            headers={"X-CSRF-Token": token},
            json={"taskAsNewRequest": True},
        )

    assert rejected.json()["ticketState"] == "RFI_SEARCH_INCOMPLETE"
    assert any(
        item["eventType"] == "rfi_search_feedback_requested" for item in detail.json()["timeline"]
    )
    assert consent.status_code == 409
    assert consent.json()["error"]["code"] == "rfi_search_feedback_required"
    assert pending_retry.json()["error"]["code"] == "rfi_search_feedback_required"


async def _reject_all(
    client: AsyncClient,
    ticket_id: str,
    token: str,
    results: Response,
) -> Response:
    response = results
    for offer in results.json()["offers"]:
        response = await client.post(
            f"/api/v1/rfi-search/{ticket_id}/offers/{offer['productId']}/reject",
            headers={"X-CSRF-Token": token},
            json={"reason": "This product does not answer the specific question."},
        )
        assert response.status_code == 200
    return response


def _make_latest_search_complete(app: FastAPI, ticket_id: str) -> None:
    services = app.state.ticket_services
    user = app.state.access_services.repository.get_user_by_username("user@example.test")
    assert user is not None
    ticket = services.tickets.get_visible_ticket(user, UUID(ticket_id))
    metric = replace(ticket.search_metrics[-1], coverage_status="complete", degraded_reason=None)
    services.tickets.save_system_update(
        replace(ticket, search_metrics=(*ticket.search_metrics[:-1], metric))
    )


def _make_latest_search_partial(app: FastAPI, ticket_id: str) -> None:
    services = app.state.ticket_services
    user = app.state.access_services.repository.get_user_by_username("user@example.test")
    assert user is not None
    ticket = services.tickets.get_visible_ticket(user, UUID(ticket_id))
    metric = replace(
        ticket.search_metrics[-1],
        coverage_status="partial",
        degraded_reason="corpus_changed",
    )
    services.tickets.save_system_update(
        replace(ticket, search_metrics=(*ticket.search_metrics[:-1], metric))
    )


def _force_refined_no_match(app: FastAPI, ticket_id: str) -> None:
    services = app.state.ticket_services
    user = app.state.access_services.repository.get_user_by_username("user@example.test")
    assert user is not None
    ticket = services.tickets.get_visible_ticket(user, UUID(ticket_id))
    services.tickets.save_system_update(
        replace(
            ticket,
            state=TicketState.NEW_TASKING_CONSENT,
            product_offers=(),
            search_evidence=(),
            visible_product_matches=(),
        )
    )
