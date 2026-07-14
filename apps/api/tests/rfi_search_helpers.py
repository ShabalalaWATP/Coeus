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


async def submitted_ticket(
    client: AsyncClient,
    csrf_token: str,
    *,
    title: str = "Regional Stability Brief",
    area_or_region: str = "Baltic ports",
    output_format: str = "assessment report",
) -> str:
    created = await client.post(
        "/api/v1/chat/messages",
        headers={"X-CSRF-Token": csrf_token},
        json={"message": "Need a briefing note for regional Baltic port activity."},
    )
    assert created.status_code == 201
    ticket_id = created.json()["id"]
    edited = await client.patch(
        f"/api/v1/tickets/{ticket_id}/intake",
        headers={"X-CSRF-Token": csrf_token},
        json={
            "title": title,
            "description": "Assess mock shipping activity and likely disruption.",
            "operationalQuestion": "What activity needs command attention?",
            "areaOrRegion": area_or_region,
            "timePeriodStart": "2026-06-01",
            "timePeriodEnd": "2026-07-01",
            "priority": "high",
            "supportedOperation": "Operation Harbour Sentinel",
            "urgencyJustification": "A patrol posture decision is due this week.",
            "deadline": "Friday",
            "requestingUnit": "Carrier Strike Group Atlas",
            "intelligenceDisciplines": "IMINT, OSINT",
            "requiredOutputFormat": output_format,
            "customerSuccessCriteria": "Identify actions for watch teams.",
        },
    )
    submitted = await client.post(
        f"/api/v1/tickets/{ticket_id}/submit",
        headers={"X-CSRF-Token": csrf_token},
    )
    assert edited.status_code == 200
    assert submitted.status_code == 200
    assert submitted.json()["state"] == "RFI_SEARCHING"
    return str(ticket_id)


def product_payload(acg_id: str, *, title: str, classification: int = 2) -> dict[str, object]:
    return {
        "title": title,
        "summary": "MOCK DATA ONLY synthetic supporting product.",
        "description": "Synthetic product metadata for RFI search testing.",
        "productType": "assessment_report",
        "sourceType": "finished_assessment",
        "ownerTeam": "RFA",
        "areaOrRegion": "Baltic ports",
        "classificationLevel": classification,
        "releasability": ["MOCK"],
        "handlingCaveats": ["MOCK DATA ONLY"],
        "tags": ["baltic", "ports"],
        "acgIds": [acg_id],
        "status": "published",
        "assets": [
            {
                "name": "supporting-brief.pdf",
                "assetType": "pdf",
                "mimeType": "application/pdf",
                "sizeBytes": 42_000,
                "sha256": "c" * 64,
            }
        ],
    }
