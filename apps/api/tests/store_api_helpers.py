from typing import Any, cast

from httpx import AsyncClient

SEED_CREDENTIAL = "CoeusLocal1!"


async def login(client: AsyncClient, username: str) -> dict[str, Any]:
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": SEED_CREDENTIAL},
    )
    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, dict)
    return cast(dict[str, Any], payload)


def product_payload(acg_id: str, *, owner_team: str = "RFA") -> dict[str, object]:
    return {
        "title": "Mock Harbour Activity Brief",
        "summary": "MOCK DATA ONLY assessment of harbour activity.",
        "description": "Synthetic product metadata for Sprint 5 testing.",
        "productType": "assessment_report",
        "sourceType": "finished_assessment",
        "ownerTeam": owner_team,
        "areaOrRegion": "Baltic ports",
        "classificationLevel": 2,
        "releasability": ["MOCK"],
        "handlingCaveats": ["MOCK DATA ONLY"],
        "tags": ["ports", "activity"],
        "acgIds": [acg_id],
        "assets": [
            {
                "name": "harbour-brief.pdf",
                "assetType": "pdf",
                "mimeType": "application/pdf",
                "sizeBytes": 42_000,
                "sha256": "a" * 64,
            }
        ],
    }
