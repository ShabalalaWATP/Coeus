import pytest
from httpx import ASGITransport, AsyncClient

from coeus.core.config import Settings
from coeus.main import create_app
from rfi_search_helpers import login, submitted_ticket


def _filler_payload(acg_id: str, index: int) -> dict[str, object]:
    """A published product that sorts before the seeded match alphabetically
    and shares nothing with the RFI query, so it can never be offered."""
    return {
        "title": f"Aardvark Archive {index:02d}",
        "summary": "MOCK DATA ONLY unrelated synthetic archive entry.",
        "description": "Synthetic filler entry about desert logistics records.",
        "productType": "sigint_mock",
        "sourceType": "sensor",
        "ownerTeam": "RFA",
        "areaOrRegion": "Sahara interior",
        "classificationLevel": 2,
        "releasability": ["MOCK"],
        "handlingCaveats": ["MOCK DATA ONLY"],
        "tags": ["filler"],
        "acgIds": [acg_id],
        "assets": [
            {
                "name": "filler.pdf",
                "assetType": "pdf",
                "mimeType": "application/pdf",
                "sizeBytes": 1_000,
                "sha256": "e" * 64,
            }
        ],
    }


@pytest.mark.asyncio
async def test_rfi_search_considers_candidates_beyond_first_store_page() -> None:
    """A matching product must still be offered when more than one store-browse
    page (12) of permitted products sorts ahead of it alphabetically."""
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    regional_acg = next(
        acg for acg in app.state.access_services.repository.list_acgs() if "ALPHA" in acg.code
    )
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        admin = await login(client, "admin@example.test")
        for index in range(1, 13):
            created = await client.post(
                "/api/v1/store/products",
                headers={"X-CSRF-Token": str(admin["csrfToken"])},
                json=_filler_payload(str(regional_acg.acg_id), index),
            )
            assert created.status_code == 201
        user = await login(client, "user@example.test")
        ticket_id = await submitted_ticket(client, str(user["csrfToken"]))
        response = await client.post(
            f"/api/v1/rfi-search/{ticket_id}/run",
            headers={"X-CSRF-Token": str(user["csrfToken"])},
        )

    assert response.status_code == 200
    payload = response.json()
    # 12 fillers + the seeded Regional Stability Brief were all searched.
    assert payload["metrics"]["candidateCount"] == 13
    assert payload["ticketState"] == "RFI_MATCH_OFFERED"
    assert "Regional Stability Brief" in [offer["title"] for offer in payload["offers"]]
    assert all(not offer["title"].startswith("Aardvark") for offer in payload["offers"])
