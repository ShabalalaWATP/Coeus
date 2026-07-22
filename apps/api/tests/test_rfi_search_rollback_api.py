from typing import cast
from uuid import UUID

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient, Response

from coeus.core.config import Settings
from coeus.domain.tickets import TicketRecord
from coeus.main import create_app
from rfi_search_helpers import login, submitted_ticket


@pytest.mark.asyncio
async def test_rfi_search_audit_failure_rolls_back_ticket(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        user = await login(client, "user@example.test")
        ticket_id = await submitted_ticket(client, str(user["csrfToken"]))
        original = _stored_ticket(app, ticket_id)
        monkeypatch.setattr(
            app.state.rfi_search_service._mutations._audit_log, "record_many", _fail_audit
        )

        with pytest.raises(RuntimeError, match="audit unavailable"):
            await client.post(
                f"/api/v1/rfi-search/{ticket_id}/run",
                headers={"X-CSRF-Token": str(user["csrfToken"])},
            )

    ticket = _stored_ticket(app, ticket_id)
    assert ticket.state == original.state
    assert ticket.product_offers == original.product_offers
    assert ticket.search_metrics == original.search_metrics
    assert ticket.timeline == original.timeline


@pytest.mark.asyncio
async def test_offer_accept_audit_failure_rolls_back_ticket(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        user = await login(client, "user@example.test")
        ticket_id = await submitted_ticket(client, str(user["csrfToken"]))
        run = await _run_search(client, ticket_id, str(user["csrfToken"]))
        product_id = run.json()["offers"][0]["productId"]
        original = _stored_ticket(app, ticket_id)
        monkeypatch.setattr(
            app.state.rfi_search_service._mutations._audit_log, "record_many", _fail_audit
        )

        with pytest.raises(RuntimeError, match="audit unavailable"):
            await client.post(
                f"/api/v1/rfi-search/{ticket_id}/offers/{product_id}/accept",
                headers={"X-CSRF-Token": str(user["csrfToken"])},
            )

    ticket = _stored_ticket(app, ticket_id)
    assert ticket.state == original.state
    assert ticket.product_offers == original.product_offers
    assert ticket.disseminations == original.disseminations
    assert ticket.search_metrics == original.search_metrics
    assert ticket.timeline == original.timeline


@pytest.mark.asyncio
async def test_offer_reject_audit_failure_rolls_back_ticket(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        user = await login(client, "user@example.test")
        ticket_id = await submitted_ticket(client, str(user["csrfToken"]))
        run = await _run_search(client, ticket_id, str(user["csrfToken"]))
        product_id = run.json()["offers"][0]["productId"]
        original = _stored_ticket(app, ticket_id)
        monkeypatch.setattr(
            app.state.rfi_search_service._mutations._audit_log, "record_many", _fail_audit
        )

        with pytest.raises(RuntimeError, match="audit unavailable"):
            await client.post(
                f"/api/v1/rfi-search/{ticket_id}/offers/{product_id}/reject",
                headers={"X-CSRF-Token": str(user["csrfToken"])},
                json={"reason": "Need fresher reporting than this mock brief."},
            )

    ticket = _stored_ticket(app, ticket_id)
    assert ticket.state == original.state
    assert ticket.product_offers == original.product_offers
    assert ticket.search_metrics == original.search_metrics
    assert ticket.timeline == original.timeline


async def _run_search(client: AsyncClient, ticket_id: str, csrf_token: str) -> Response:
    response = await client.post(
        f"/api/v1/rfi-search/{ticket_id}/run",
        headers={"X-CSRF-Token": csrf_token},
    )
    assert response.status_code == 200
    return response


def _fail_audit(*_args: object, **_kwargs: object) -> None:
    raise RuntimeError("audit unavailable")


def _app() -> FastAPI:
    return create_app(
        Settings(
            environment="test",
            argon2_memory_cost=8_192,
            automatic_request_discovery_enabled=False,
        )
    )


def _stored_ticket(app: FastAPI, ticket_id: str) -> TicketRecord:
    ticket = app.state.ticket_services.tickets._repository.get(UUID(ticket_id))
    assert ticket is not None
    return cast(TicketRecord, ticket)
