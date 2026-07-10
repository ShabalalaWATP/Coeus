import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from coeus.core.config import Settings
from coeus.main import create_app
from rfi_search_helpers import login


def _client(app: FastAPI) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")


async def _draft_ticket(client: AsyncClient, csrf: str) -> str:
    created = await client.post(
        "/api/v1/chat/messages",
        headers={"X-CSRF-Token": csrf},
        json={"message": "Need a routine brief on port activity."},
    )
    assert created.status_code == 201
    return str(created.json()["id"])


@pytest.mark.asyncio
async def test_admin_write_all_permission_still_allows_intake_edits() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))

    async with _client(app) as user, _client(app) as admin:
        user_session = await login(user, "user@example.test")
        ticket_id = await _draft_ticket(user, str(user_session["csrfToken"]))
        admin_session = await login(admin, "admin@example.test")
        edited = await admin.patch(
            f"/api/v1/tickets/{ticket_id}/intake",
            headers={"X-CSRF-Token": str(admin_session["csrfToken"])},
            json={"priority": "routine"},
        )

    assert edited.status_code == 200
    assert edited.json()["intake"]["priority"] == "routine"


@pytest.mark.asyncio
async def test_submitted_ticket_intake_is_no_longer_editable() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))

    async with _client(app) as client:
        session = await login(client, "user@example.test")
        csrf = str(session["csrfToken"])
        ticket_id = await _draft_ticket(client, csrf)
        await client.patch(
            f"/api/v1/tickets/{ticket_id}/intake",
            headers={"X-CSRF-Token": csrf},
            json={
                "title": "Regional Port Activity",
                "description": "Assess mock shipping activity and likely disruption.",
                "operationalQuestion": "What activity needs command attention?",
                "areaOrRegion": "Baltic ports",
                "priority": "high",
                "requiredOutputFormat": "Briefing note",
                "customerSuccessCriteria": "Identify actions for watch teams.",
            },
        )
        await client.post(
            f"/api/v1/tickets/{ticket_id}/submit",
            headers={"X-CSRF-Token": csrf},
        )
        late_edit = await client.patch(
            f"/api/v1/tickets/{ticket_id}/intake",
            headers={"X-CSRF-Token": csrf},
            json={"priority": "routine"},
        )

    assert late_edit.status_code == 409
    assert late_edit.json()["error"]["code"] == "ticket_not_editable"


@pytest.mark.asyncio
async def test_admin_write_all_permission_allows_information_on_visible_ticket() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))

    async with _client(app) as user, _client(app) as admin:
        user_session = await login(user, "user@example.test")
        ticket_id = await _draft_ticket(user, str(user_session["csrfToken"]))
        admin_session = await login(admin, "admin@example.test")
        response = await admin.post(
            f"/api/v1/tickets/{ticket_id}/timeline",
            headers={"X-CSRF-Token": str(admin_session["csrfToken"])},
            json={"body": "Admin adds operational context."},
        )

    assert response.status_code == 200
    assert response.json()["timeline"][-1]["body"] == "Admin adds operational context."
