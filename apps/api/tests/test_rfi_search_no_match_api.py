import pytest
from httpx import ASGITransport, AsyncClient

from coeus.core.config import Settings
from coeus.main import create_app
from rfi_search_helpers import login


@pytest.mark.asyncio
async def test_rfi_search_routes_to_assessment_when_no_offer_exceeds_threshold() -> None:
    settings = Settings(
        environment="test",
        argon2_memory_cost=8_192,
        persistence_provider="memory",
    )
    app = create_app(settings)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        user = await login(client, "user@example.test")
        created = await client.post(
            "/api/v1/chat/messages",
            headers={"X-CSRF-Token": str(user["csrfToken"])},
            json={"message": "Need a spreadsheet forecast for mock Martian crop yields."},
        )
        ticket_id = created.json()["id"]
        edited = await client.patch(
            f"/api/v1/tickets/{ticket_id}/intake",
            headers={"X-CSRF-Token": str(user["csrfToken"])},
            json={
                "title": "Martian Crop Forecast",
                "description": "Forecast mock agricultural yields on Mars farms.",
                "operationalQuestion": "What crop yield is expected?",
                "areaOrRegion": "Mars farms",
                "priority": "routine",
                "requiredOutputFormat": "spreadsheet",
                "customerSuccessCriteria": "Estimate crop output.",
                "knownContext": None,
            },
        )
        submitted = await client.post(
            f"/api/v1/tickets/{ticket_id}/submit",
            headers={"X-CSRF-Token": str(user["csrfToken"])},
        )
        response = await client.post(
            f"/api/v1/rfi-search/{ticket_id}/run",
            headers={"X-CSRF-Token": str(user["csrfToken"])},
        )

    assert created.status_code == 201
    assert edited.status_code == 200
    assert submitted.status_code == 200
    assert response.status_code == 200
    assert response.json()["ticketState"] == "ROUTE_ASSESSMENT"
    assert response.json()["offers"] == []
    assert response.json()["metrics"]["offeredCount"] == 0
