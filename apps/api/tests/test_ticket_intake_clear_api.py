import pytest
from httpx import ASGITransport, AsyncClient

from coeus.core.config import Settings
from coeus.main import create_app
from ticket_api_helpers import login


@pytest.mark.asyncio
async def test_explicit_clear_preserves_omitted_intake_fields() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        session = await login(client)
        created = await client.post(
            "/api/v1/chat/messages",
            headers={"X-CSRF-Token": str(session["csrfToken"])},
            json={"message": "Need a brief on regional port activity."},
        )
        ticket_id = created.json()["id"]
        original_description = created.json()["intake"]["description"]
        cleared = await client.patch(
            f"/api/v1/tickets/{ticket_id}/intake",
            headers={"X-CSRF-Token": str(session["csrfToken"])},
            json={"title": None},
        )

    assert cleared.status_code == 200
    assert cleared.json()["intake"]["title"] is None
    assert cleared.json()["intake"]["description"] == original_description
    assert "title" in cleared.json()["intake"]["missingInformation"]
