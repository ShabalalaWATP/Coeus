import pytest
from httpx import ASGITransport, AsyncClient

from coeus.core.config import Settings
from coeus.main import create_app
from rfi_search_helpers import login, submitted_ticket


@pytest.mark.asyncio
async def test_viewer_collaborator_cannot_run_rfi_search() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        user = await login(client, "user@example.test")
        ticket_id = await submitted_ticket(client, str(user["csrfToken"]))
        tagged = await client.post(
            f"/api/v1/tickets/{ticket_id}/collaborators",
            headers={"X-CSRF-Token": str(user["csrfToken"])},
            json={"username": "colleague@example.test", "access": "viewer"},
        )
        colleague = await login(client, "colleague@example.test")
        denied = await client.post(
            f"/api/v1/rfi-search/{ticket_id}/run",
            headers={"X-CSRF-Token": str(colleague["csrfToken"])},
        )

    assert tagged.status_code == 200
    assert denied.status_code == 404
    assert denied.json()["error"]["code"] == "ticket_not_found"
