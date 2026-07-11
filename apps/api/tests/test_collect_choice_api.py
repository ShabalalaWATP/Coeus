import pytest
from httpx import ASGITransport, AsyncClient

from coeus.core.config import Settings
from coeus.main import create_app
from rfi_search_helpers import login
from routing_helpers import route_assessment_ticket


async def _collect_choice_ticket(client: AsyncClient) -> str:
    """Walk a collection-led ticket through the JIOC decision to COLLECT_CHOICE."""
    user = await login(client, "user@example.test")
    ticket_id = await route_assessment_ticket(
        client,
        str(user["csrfToken"]),
        title="Arctic Sensor Collection",
        area_or_region="Arctic fisheries",
        output_format="collection plan",
    )
    jioc = await login(client, "jioc.team@example.test")
    await client.post(
        f"/api/v1/routing/{ticket_id}/run",
        headers={"X-CSRF-Token": str(jioc["csrfToken"])},
    )
    approved = await client.post(
        f"/api/v1/routing/{ticket_id}/approve",
        headers={"X-CSRF-Token": str(jioc["csrfToken"])},
        json={"route": "cm"},
    )
    assert approved.status_code == 200
    assert approved.json()["state"] == "COLLECT_CHOICE"
    await login(client, "user@example.test")
    return ticket_id


@pytest.mark.asyncio
async def test_cm_approval_pauses_for_the_customer_and_notifies_in_chat() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        ticket_id = await _collect_choice_ticket(client)
        ticket = await client.get(f"/api/v1/tickets/{ticket_id}")

    payload = ticket.json()
    assert payload["state"] == "COLLECT_CHOICE"
    assert payload["collectDisposition"] is None
    assert payload["messages"][-1]["author"] == "assistant"
    assert "raw collect" in payload["messages"][-1]["body"]
    assert payload["timeline"][-1]["eventType"] == "collect_choice_requested"


@pytest.mark.asyncio
async def test_customer_chooses_raw_collect_only() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        ticket_id = await _collect_choice_ticket(client)
        user = await login(client, "user@example.test")
        chosen = await client.post(
            f"/api/v1/tickets/{ticket_id}/collect-choice",
            headers={"X-CSRF-Token": str(user["csrfToken"])},
            json={"analysed": False},
        )

    assert chosen.status_code == 200
    assert chosen.json()["state"] == "ANALYST_ASSIGNMENT"
    assert chosen.json()["collectDisposition"] == "raw"


@pytest.mark.asyncio
async def test_customer_chooses_collect_plus_analysis() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        ticket_id = await _collect_choice_ticket(client)
        user = await login(client, "user@example.test")
        chosen = await client.post(
            f"/api/v1/tickets/{ticket_id}/collect-choice",
            headers={"X-CSRF-Token": str(user["csrfToken"])},
            json={"analysed": True},
        )
        cm_manager = await login(client, "collection.manager@example.test")
        cm_queue = await client.get("/api/v1/routing/cm/queue")

    assert chosen.status_code == 200
    assert chosen.json()["state"] == "ANALYST_ASSIGNMENT"
    assert chosen.json()["collectDisposition"] == "analysed"
    # The CM manager's team queue now owns the ticket.
    assert cm_queue.status_code == 200
    assert ticket_id in [item["ticketId"] for item in cm_queue.json()["tickets"]]
    assert cm_manager["user"]["username"] == "collection.manager@example.test"


@pytest.mark.asyncio
async def test_only_the_requester_can_choose_and_only_in_the_right_state() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        ticket_id = await _collect_choice_ticket(client)
        colleague = await login(client, "colleague@example.test")
        not_owner = await client.post(
            f"/api/v1/tickets/{ticket_id}/collect-choice",
            headers={"X-CSRF-Token": str(colleague["csrfToken"])},
            json={"analysed": False},
        )
        user = await login(client, "user@example.test")
        await client.post(
            f"/api/v1/tickets/{ticket_id}/collect-choice",
            headers={"X-CSRF-Token": str(user["csrfToken"])},
            json={"analysed": False},
        )
        repeated = await client.post(
            f"/api/v1/tickets/{ticket_id}/collect-choice",
            headers={"X-CSRF-Token": str(user["csrfToken"])},
            json={"analysed": True},
        )

    # Non-owners cannot even see the ticket, so the check reads as not-found.
    assert not_owner.status_code == 404
    assert repeated.status_code == 409
    assert repeated.json()["error"]["code"] == "invalid_ticket_state"
