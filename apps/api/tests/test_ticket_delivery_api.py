from dataclasses import replace
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient

from coeus.core.config import Settings
from coeus.domain.enums import TicketState
from coeus.main import create_app
from rfi_search_helpers import login


def _app_and_client() -> tuple[object, AsyncClient]:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    return app, AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")


async def _draft_ticket(client: AsyncClient, csrf: str) -> str:
    response = await client.post(
        "/api/v1/chat/messages",
        headers={"X-CSRF-Token": csrf},
        json={"message": "Need a brief on regional port activity."},
    )
    assert response.status_code == 201
    return str(response.json()["id"])


def _force_state(app: object, ticket_id: str, state: TicketState) -> None:
    repository = app.state.ticket_services.tickets._repository  # type: ignore[attr-defined]
    ticket = repository.get(UUID(ticket_id))
    assert ticket is not None
    repository.save(replace(ticket, state=state))


@pytest.mark.asyncio
async def test_owner_confirms_delivery_and_closes_the_ticket() -> None:
    app, client = _app_and_client()
    async with client:
        user = await login(client, "user@example.test")
        ticket_id = await _draft_ticket(client, str(user["csrfToken"]))
        _force_state(app, ticket_id, TicketState.DISSEMINATION_READY)

        confirmed = await client.post(
            f"/api/v1/tickets/{ticket_id}/confirm-delivery",
            headers={"X-CSRF-Token": str(user["csrfToken"])},
        )
        repeat = await client.post(
            f"/api/v1/tickets/{ticket_id}/confirm-delivery",
            headers={"X-CSRF-Token": str(user["csrfToken"])},
        )
        await login(client, "admin@example.test")
        audit = await client.get("/api/v1/audit")

    assert confirmed.status_code == 200
    assert confirmed.json()["state"] == "CLOSED_DELIVERED"
    assert confirmed.json()["timeline"][-1]["eventType"] == "delivery_confirmed"
    assert repeat.status_code == 409
    assert repeat.json()["error"]["code"] == "invalid_ticket_state"
    event_types = [event["eventType"] for event in audit.json()["events"]]
    assert "ticket_delivery_confirmed" in event_types


@pytest.mark.asyncio
async def test_confirm_delivery_audit_failure_rolls_back_ticket(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app, client = _app_and_client()
    async with client:
        user = await login(client, "user@example.test")
        ticket_id = await _draft_ticket(client, str(user["csrfToken"]))
        _force_state(app, ticket_id, TicketState.DISSEMINATION_READY)
        original = _stored_ticket(app, ticket_id)
        monkeypatch.setattr(app.state.ticket_lifecycle_service._audit_log, "record", _fail_audit)

        with pytest.raises(RuntimeError, match="audit unavailable"):
            await client.post(
                f"/api/v1/tickets/{ticket_id}/confirm-delivery",
                headers={"X-CSRF-Token": str(user["csrfToken"])},
            )

    ticket = _stored_ticket(app, ticket_id)
    assert ticket.state == original.state
    assert ticket.timeline == original.timeline


@pytest.mark.asyncio
async def test_confirm_delivery_rejects_non_owner_and_wrong_state() -> None:
    app, client = _app_and_client()
    async with client:
        user = await login(client, "user@example.test")
        ticket_id = await _draft_ticket(client, str(user["csrfToken"]))

        premature = await client.post(
            f"/api/v1/tickets/{ticket_id}/confirm-delivery",
            headers={"X-CSRF-Token": str(user["csrfToken"])},
        )
        assert premature.status_code == 409
        assert premature.json()["error"]["code"] == "invalid_ticket_state"

        _force_state(app, ticket_id, TicketState.DISSEMINATION_READY)
        admin = await login(client, "admin@example.test")
        forbidden = await client.post(
            f"/api/v1/tickets/{ticket_id}/confirm-delivery",
            headers={"X-CSRF-Token": str(admin["csrfToken"])},
        )
        assert forbidden.status_code == 403
        assert forbidden.json()["error"]["code"] == "forbidden"

        await login(client, "user@example.test")
        missing_csrf = await client.post(f"/api/v1/tickets/{ticket_id}/confirm-delivery")
        assert missing_csrf.status_code == 403
        assert missing_csrf.json()["error"]["code"] == "csrf_failed"


def _fail_audit(*_args: object, **_kwargs: object) -> None:
    raise RuntimeError("audit unavailable")


def _stored_ticket(app: object, ticket_id: str):
    ticket = app.state.ticket_services.tickets._repository.get(UUID(ticket_id))
    assert ticket is not None
    return ticket
