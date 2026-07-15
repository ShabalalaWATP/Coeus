import pytest
from httpx import ASGITransport, AsyncClient

from coeus.core.config import Settings
from coeus.main import create_app
from rfi_search_helpers import login, submitted_ticket


@pytest.mark.asyncio
async def test_ticket_response_hides_rfi_matches_from_unauthorised_collaborator() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    regional_product = next(
        product
        for product in app.state.store_services.repository.list_products()
        if product.metadata.title == "Regional Stability Brief"
    )
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        user = await login(client, "user@example.test")
        ticket_id = await submitted_ticket(client, str(user["csrfToken"]))
        tagged = await client.post(
            f"/api/v1/tickets/{ticket_id}/collaborators",
            headers={"X-CSRF-Token": str(user["csrfToken"])},
            json={"username": "collection.team@example.test", "access": "viewer"},
        )
        run = await client.post(
            f"/api/v1/rfi-search/{ticket_id}/run",
            headers={"X-CSRF-Token": str(user["csrfToken"])},
        )
        owner_ticket = await client.get(f"/api/v1/tickets/{ticket_id}")

        await login(client, "collection.team@example.test")
        collaborator_ticket = await client.get(f"/api/v1/tickets/{ticket_id}")
        collaborator_results = await client.get(f"/api/v1/rfi-search/{ticket_id}/results")

    assert tagged.status_code == 200
    assert run.status_code == 200
    assert owner_ticket.json()["visibleProductMatches"] == ["Regional Stability Brief"]
    assert collaborator_ticket.json()["visibleProductMatches"] == []
    assert collaborator_results.json()["offers"] == []
    assert str(regional_product.product_id) not in collaborator_results.text
