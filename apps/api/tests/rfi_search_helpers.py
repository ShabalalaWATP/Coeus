from dataclasses import replace
from typing import Any, cast
from uuid import UUID

from fastapi import FastAPI
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
    restrictions: str | None = None,
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
            "timePeriodStart": "2026-03-01",
            "timePeriodEnd": "2026-04-30",
            "priority": "high",
            "supportedOperation": "Operation Harbour Sentinel",
            "urgencyJustification": "A patrol posture decision is due this week.",
            "deadline": "Friday",
            "requestingUnit": "Carrier Strike Group Atlas",
            "intelligenceDisciplines": "IMINT, OSINT",
            "requiredOutputFormat": output_format,
            "restrictionsOrCaveats": restrictions,
            "customerSuccessCriteria": "Identify actions for watch teams.",
        },
    )
    submitted = await client.post(
        f"/api/v1/tickets/{ticket_id}/submit",
        headers={"X-CSRF-Token": csrf_token},
    )
    assert edited.status_code == 200
    assert submitted.status_code == 200
    assert submitted.json()["state"] in {
        "RFI_SEARCHING",
        "RFI_MATCH_OFFERED",
        "RFI_SEARCH_INCOMPLETE",
        "NEW_TASKING_CONSENT",
    }
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


def ensure_search_index_ready(app: FastAPI) -> None:
    """Build the evaluated mock index required for a definitive no-match."""
    if app.state.search_configuration_service.state().index_status == "ready":
        return
    admin = app.state.access_services.repository.get_user_by_username("admin@example.test")
    assert admin is not None
    profile = app.state.search_indexing_service.start(admin.user_id)
    app.state.search_indexing_service.run(profile)
    assert app.state.search_configuration_service.state().index_status == "ready"


def mark_search_complete_for_downstream_fixture(app: FastAPI, ticket_id: str) -> None:
    """Isolate downstream workflow tests from intentionally degraded seed assets."""
    repository = app.state.ticket_services.tickets._repository
    ticket = repository.get(UUID(ticket_id))
    assert ticket is not None and ticket.search_metrics
    metric = replace(
        ticket.search_metrics[-1],
        coverage_status="complete",
        degraded_reason=None,
    )
    repository.save(replace(ticket, search_metrics=(*ticket.search_metrics[:-1], metric)))
