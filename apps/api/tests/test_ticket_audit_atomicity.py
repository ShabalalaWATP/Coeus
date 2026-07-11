from copy import deepcopy

import pytest
from httpx import ASGITransport, AsyncClient

from coeus.core.config import Settings
from coeus.main import create_app
from ticket_api_helpers import fail_audit, login, stored_ticket


@pytest.mark.asyncio
async def test_new_chat_is_removed_when_audit_confirmation_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        session = await login(client)
        repository = app.state.ticket_services.tickets._repository
        baseline = repository.list_tickets()
        monkeypatch.setattr(
            app.state.ticket_services.conversations._audit_log, "record", fail_audit
        )

        response = await client.post(
            "/api/v1/chat/messages",
            headers={"X-CSRF-Token": str(session["csrfToken"])},
            json={"message": "Need a synthetic regional activity brief."},
        )

    assert response.status_code == 500
    assert repository.list_tickets() == baseline


@pytest.mark.asyncio
async def test_existing_chat_is_restored_exactly_when_audit_confirmation_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        session = await login(client)
        created = await client.post(
            "/api/v1/chat/messages",
            headers={"X-CSRF-Token": str(session["csrfToken"])},
            json={"message": "Need a synthetic regional activity brief."},
        )
        ticket_id = created.json()["id"]
        original = deepcopy(stored_ticket(app, ticket_id))
        monkeypatch.setattr(
            app.state.ticket_services.conversations._audit_log, "record", fail_audit
        )

        response = await client.post(
            "/api/v1/chat/messages",
            headers={"X-CSRF-Token": str(session["csrfToken"])},
            json={"ticketId": ticket_id, "message": "Add the latest synthetic reporting."},
        )

    assert response.status_code == 500
    assert stored_ticket(app, ticket_id) == original


@pytest.mark.asyncio
async def test_intake_is_restored_exactly_when_audit_confirmation_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        session = await login(client)
        created = await client.post(
            "/api/v1/chat/messages",
            headers={"X-CSRF-Token": str(session["csrfToken"])},
            json={"message": "Need a synthetic regional activity brief."},
        )
        ticket_id = created.json()["id"]
        original = deepcopy(stored_ticket(app, ticket_id))
        monkeypatch.setattr(app.state.ticket_services.tickets._audit_log, "record", fail_audit)

        response = await client.patch(
            f"/api/v1/tickets/{ticket_id}/intake",
            headers={"X-CSRF-Token": str(session["csrfToken"])},
            json={"priority": "critical", "title": "Changed synthetic requirement"},
        )

    assert response.status_code == 500
    assert stored_ticket(app, ticket_id) == original
