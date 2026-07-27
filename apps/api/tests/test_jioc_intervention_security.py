from datetime import UTC, datetime
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from coeus.main import create_app
from rfi_search_helpers import login
from routing_helpers import submitted_ticket
from test_jioc_routing_agent import _prepare, _settings


@pytest.mark.asyncio
async def test_intervention_rejects_blank_reasons_and_stale_oversight_versions() -> None:
    app = create_app(_settings())
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        customer = await login(client, "user@example.test")
        ticket_id = await submitted_ticket(
            client,
            str(customer["csrfToken"]),
            title="Synthetic stale intervention requirement",
            area_or_region="Baltic ports",
        )
        prepared = _prepare(app, ticket_id, description="Assess the available reporting.")
        app.state.jioc_routing_agent_service.route(prepared.ticket_id)
        manager = await login(client, "jioc.team@example.test")
        oversight = await client.get("/api/v1/routing/oversight")
        expected = next(
            task["updatedAt"] for task in oversight.json()["tasks"] if task["ticketId"] == ticket_id
        )
        missing_version = await client.post(
            f"/api/v1/routing/{ticket_id}/intervene",
            headers={"X-CSRF-Token": str(manager["csrfToken"])},
            json={"action": "hold", "reason": "Investigate risk."},
        )
        blank = await client.post(
            f"/api/v1/routing/{ticket_id}/intervene",
            headers={"X-CSRF-Token": str(manager["csrfToken"])},
            json={"action": "hold", "expectedUpdatedAt": expected, "reason": "   "},
        )
        held = await client.post(
            f"/api/v1/routing/{ticket_id}/intervene",
            headers={"X-CSRF-Token": str(manager["csrfToken"])},
            json={"action": "hold", "expectedUpdatedAt": expected, "reason": "Investigate risk."},
        )
        stale = await client.post(
            f"/api/v1/routing/{ticket_id}/intervene",
            headers={"X-CSRF-Token": str(manager["csrfToken"])},
            json={"action": "resume", "expectedUpdatedAt": expected, "reason": "Risk cleared."},
        )

    assert missing_version.status_code == 428
    assert missing_version.json()["error"]["code"] == "ticket_version_required"
    assert blank.status_code == 422
    assert held.status_code == 200
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "ticket_changed"


@pytest.mark.asyncio
async def test_jioc_intervention_rejects_unauthorised_missing_and_invalid_work() -> None:
    app = create_app(_settings())
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        customer = await login(client, "user@example.test")
        created = await client.post(
            "/api/v1/chat/messages",
            headers={"X-CSRF-Token": str(customer["csrfToken"])},
            json={"message": "Need a synthetic oversight test request."},
        )
        ticket_id = created.json()["id"]
        forbidden = await client.post(
            f"/api/v1/routing/{ticket_id}/intervene",
            headers={"X-CSRF-Token": str(customer["csrfToken"])},
            json={
                "action": "hold",
                "expectedUpdatedAt": datetime.now(UTC).isoformat(),
                "reason": "Synthetic unauthorised intervention.",
            },
        )
        manager = await login(client, "jioc.team@example.test")
        missing = await client.post(
            f"/api/v1/routing/{uuid4()}/intervene",
            headers={"X-CSRF-Token": str(manager["csrfToken"])},
            json={
                "action": "hold",
                "expectedUpdatedAt": datetime.now(UTC).isoformat(),
                "reason": "Synthetic missing request.",
            },
        )
        invalid = {}
        for action in ("hold", "resume", "send_to_review"):
            response = await client.post(
                f"/api/v1/routing/{ticket_id}/intervene",
                headers={"X-CSRF-Token": str(manager["csrfToken"])},
                json={
                    "action": action,
                    "expectedUpdatedAt": created.json()["updatedAt"],
                    "reason": "Synthetic invalid state.",
                },
            )
            invalid[action] = response.status_code

    assert forbidden.status_code == 403
    assert missing.status_code == 404
    assert invalid == {"hold": 409, "resume": 409, "send_to_review": 409}
