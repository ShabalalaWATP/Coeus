import pytest
from httpx import ASGITransport, AsyncClient

from coeus.core.config import Settings
from coeus.main import create_app
from rfi_search_helpers import login
from test_qc_api import _acg_id, _approval_payload, _submitted_qc_ticket


async def _ticket_awaiting_release(client: AsyncClient, app: object) -> str:
    ticket_id = await _submitted_qc_ticket(client, app, "Release Arctic product")
    qc_manager = await login(client, "qc.manager@example.test")
    approved = await client.post(
        f"/api/v1/qc/products/{ticket_id}/approve",
        headers={"X-CSRF-Token": str(qc_manager["csrfToken"])},
        json=_approval_payload(_acg_id(app, "ACG-ALPHA-REGIONAL")),
    )
    assert approved.status_code == 200
    return ticket_id


@pytest.mark.asyncio
async def test_route_manager_releases_and_customer_is_notified() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        ticket_id = await _ticket_awaiting_release(client, app)

        manager = await login(client, "rfa.manager@example.test")
        release_queue = await client.get("/api/v1/routing/rfa/release-queue")
        assert release_queue.status_code == 200
        assert ticket_id in [ticket["ticketId"] for ticket in release_queue.json()["tickets"]]

        released = await client.post(
            f"/api/v1/routing/{ticket_id}/release",
            headers={"X-CSRF-Token": str(manager["csrfToken"])},
            json={"route": "rfa"},
        )
        assert released.status_code == 200
        assert released.json()["state"] == "DISSEMINATION_READY"

        emptied = await client.get("/api/v1/routing/rfa/release-queue")
        assert emptied.json()["tickets"] == []

        await login(client, "user@example.test")
        tickets = await client.get("/api/v1/tickets")
        released_ticket = next(
            ticket for ticket in tickets.json()["tickets"] if ticket["id"] == ticket_id
        )
        assert len(released_ticket["releasedProductIds"]) == 1
        product_id = released_ticket["releasedProductIds"][0]

        search = await client.get("/api/v1/store/products?query=Release%20Arctic")
        assert product_id in {product["id"] for product in search.json()["products"]}

        notifications = await client.get("/api/v1/notifications")
        assert notifications.status_code == 200
        assert notifications.json()["unread"] == 1
        notification = notifications.json()["notifications"][0]
        assert notification["kind"] == "product_released"
        assert notification["linkPath"] == f"/store/products/{product_id}"

        user = await login(client, "user@example.test")
        read = await client.post(
            f"/api/v1/notifications/{notification['id']}/read",
            headers={"X-CSRF-Token": str(user["csrfToken"])},
        )
        assert read.status_code == 200
        assert read.json()["read"] is True

        await login(client, "admin@example.test")
        audit = await client.get("/api/v1/audit")
        event_types = [event["eventType"] for event in audit.json()["events"]]
        assert "product_released" in event_types
        assert "email_recorded" in event_types


@pytest.mark.asyncio
async def test_release_requires_matching_route_manager_and_state() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        ticket_id = await _ticket_awaiting_release(client, app)

        analyst = await login(client, "analyst@example.test")
        forbidden = await client.post(
            f"/api/v1/routing/{ticket_id}/release",
            headers={"X-CSRF-Token": str(analyst["csrfToken"])},
            json={"route": "rfa"},
        )
        assert forbidden.status_code == 403

        cm_manager = await login(client, "collection.manager@example.test")
        wrong_route = await client.post(
            f"/api/v1/routing/{ticket_id}/release",
            headers={"X-CSRF-Token": str(cm_manager["csrfToken"])},
            json={"route": "cm"},
        )
        assert wrong_route.status_code == 409
        cm_queue = await client.get("/api/v1/routing/cm/release-queue")
        assert cm_queue.json()["tickets"] == []

        manager = await login(client, "rfa.manager@example.test")
        missing_csrf = await client.post(
            f"/api/v1/routing/{ticket_id}/release",
            json={"route": "rfa"},
        )
        assert missing_csrf.status_code == 403
        assert missing_csrf.json()["error"]["code"] == "csrf_failed"

        bad_route = await client.post(
            f"/api/v1/routing/{ticket_id}/release",
            headers={"X-CSRF-Token": str(manager["csrfToken"])},
            json={"route": "sideways"},
        )
        assert bad_route.status_code == 422

        released = await client.post(
            f"/api/v1/routing/{ticket_id}/release",
            headers={"X-CSRF-Token": str(manager["csrfToken"])},
            json={"route": "rfa"},
        )
        assert released.status_code == 200

        repeat = await client.post(
            f"/api/v1/routing/{ticket_id}/release",
            headers={"X-CSRF-Token": str(manager["csrfToken"])},
            json={"route": "rfa"},
        )
        assert repeat.status_code == 409


@pytest.mark.asyncio
async def test_release_rejects_tickets_still_in_qc() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        ticket_id = await _submitted_qc_ticket(client, app, "Unapproved release product")
        manager = await login(client, "rfa.manager@example.test")
        premature = await client.post(
            f"/api/v1/routing/{ticket_id}/release",
            headers={"X-CSRF-Token": str(manager["csrfToken"])},
            json={"route": "rfa"},
        )

    assert premature.status_code == 409
    assert premature.json()["error"]["code"] == "invalid_ticket_state"
