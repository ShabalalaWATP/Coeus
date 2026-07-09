from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient

from coeus.core.config import Settings
from coeus.domain.access import ProductStatus
from coeus.domain.enums import TicketState
from coeus.main import create_app
from rfi_search_helpers import login
from test_qc_api import _acg_id, _approval_payload, _submitted_qc_ticket


async def _ticket_awaiting_release(client: AsyncClient, app: object) -> str:
    ticket_id = await _submitted_qc_ticket(client, app, "Release Arctic product")
    qc_manager = await login(client, "qc.manager@example.test")
    approved = await client.post(
        f"/api/v1/qc/products/{ticket_id}/approve",
        headers={"X-CSRF-Token": str(qc_manager["csrfToken"])},
        json=_approval_payload(_acg_id(app, "ACG-EU-CYBER")),
    )
    assert approved.status_code == 200
    return ticket_id


@pytest.mark.asyncio
async def test_owning_manager_releases_and_customer_is_notified() -> None:
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
async def test_release_requires_matching_owning_manager_and_state() -> None:
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
async def test_failed_release_does_not_publish_product() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        ticket_id = await _submitted_qc_ticket(client, app, "Too restricted release product")
        qc_manager = await login(client, "qc.manager@example.test")
        payload = _approval_payload(_acg_id(app, "ACG-EU-CYBER"))
        payload["classificationLevel"] = 4
        approved = await client.post(
            f"/api/v1/qc/products/{ticket_id}/approve",
            headers={"X-CSRF-Token": str(qc_manager["csrfToken"])},
            json=payload,
        )
        manager = await login(client, "rfa.manager@example.test")
        failed = await client.post(
            f"/api/v1/routing/{ticket_id}/release",
            headers={"X-CSRF-Token": str(manager["csrfToken"])},
            json={"route": "rfa"},
        )

    assert approved.status_code == 200
    ticket = app.state.ticket_services.tickets._repository.get(UUID(ticket_id))
    assert ticket is not None
    product_id = ticket.product_index_records[-1].product_id
    product = app.state.store_services.repository.get_product(product_id)
    assert failed.status_code == 404
    assert failed.json()["error"]["code"] == "product_not_found"
    assert product is not None
    assert product.metadata.status == ProductStatus.DRAFT
    assert ticket.state == TicketState.MANAGER_RELEASE
    assert ticket.disseminations == ()


@pytest.mark.asyncio
async def test_release_ticket_update_failure_rolls_back_published_product(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        ticket_id = await _ticket_awaiting_release(client, app)
        ticket = app.state.ticket_services.tickets._repository.get(UUID(ticket_id))
        assert ticket is not None
        product_id = ticket.product_index_records[-1].product_id
        product = app.state.store_services.repository.get_product(product_id)
        assert product is not None
        assert product.metadata.status == ProductStatus.DRAFT
        manager = await login(client, "rfa.manager@example.test")
        tickets = app.state.ticket_services.tickets
        original = tickets.save_system_update

        def fail_save(_ticket):
            raise RuntimeError("simulated release persistence failure")

        monkeypatch.setattr(tickets, "save_system_update", fail_save)
        with pytest.raises(RuntimeError, match="simulated release persistence failure"):
            await client.post(
                f"/api/v1/routing/{ticket_id}/release",
                headers={"X-CSRF-Token": str(manager["csrfToken"])},
                json={"route": "rfa"},
            )
        monkeypatch.setattr(tickets, "save_system_update", original)

        rolled_back = app.state.store_services.repository.get_product(product_id)
        current_ticket = app.state.ticket_services.tickets._repository.get(UUID(ticket_id))
        notifications = await client.get("/api/v1/notifications")

    assert rolled_back is not None
    assert rolled_back.metadata.status == ProductStatus.DRAFT
    assert current_ticket is not None
    assert current_ticket.state == TicketState.MANAGER_RELEASE
    assert current_ticket.disseminations == ()
    assert notifications.json()["unread"] == 0


@pytest.mark.asyncio
async def test_release_audit_failure_rolls_back_ticket_and_product(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        ticket_id = await _ticket_awaiting_release(client, app)
        ticket = app.state.ticket_services.tickets._repository.get(UUID(ticket_id))
        assert ticket is not None
        product_id = ticket.product_index_records[-1].product_id
        product = app.state.store_services.repository.get_product(product_id)
        assert product is not None
        assert product.metadata.status == ProductStatus.DRAFT
        manager = await login(client, "rfa.manager@example.test")
        audit_log = app.state.product_release_service._audit_log
        original_audit_record = audit_log.record

        def fail_audit(*_args: object, **_kwargs: object) -> None:
            raise RuntimeError("release audit unavailable")

        monkeypatch.setattr(audit_log, "record", fail_audit)
        with pytest.raises(RuntimeError, match="release audit unavailable"):
            await client.post(
                f"/api/v1/routing/{ticket_id}/release",
                headers={"X-CSRF-Token": str(manager["csrfToken"])},
                json={"route": "rfa"},
            )
        monkeypatch.setattr(audit_log, "record", original_audit_record)

        rolled_back = app.state.store_services.repository.get_product(product_id)
        current_ticket = app.state.ticket_services.tickets._repository.get(UUID(ticket_id))
        await login(client, "user@example.test")
        notifications = await client.get("/api/v1/notifications")
        search = await client.get("/api/v1/store/products?query=Release%20Arctic")

    assert rolled_back is not None
    assert rolled_back.metadata.status == ProductStatus.DRAFT
    assert current_ticket is not None
    assert current_ticket.state == TicketState.MANAGER_RELEASE
    assert current_ticket.disseminations == ()
    assert current_ticket.feedback_requests == ()
    assert notifications.json()["unread"] == 0
    assert str(product_id) not in {product["id"] for product in search.json()["products"]}


@pytest.mark.asyncio
async def test_release_succeeds_when_notification_side_effect_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        ticket_id = await _ticket_awaiting_release(client, app)

        def fail_notify(*_args: object, **_kwargs: object) -> None:
            raise RuntimeError("notification backend unavailable")

        monkeypatch.setattr(app.state.notification_service, "notify", fail_notify)
        manager = await login(client, "rfa.manager@example.test")
        released = await client.post(
            f"/api/v1/routing/{ticket_id}/release",
            headers={"X-CSRF-Token": str(manager["csrfToken"])},
            json={"route": "rfa"},
        )
        await login(client, "admin@example.test")
        audit = await client.get("/api/v1/audit")

    ticket = app.state.ticket_services.tickets._repository.get(UUID(ticket_id))
    assert ticket is not None
    product = app.state.store_services.repository.get_product(
        ticket.product_index_records[-1].product_id
    )
    assert released.status_code == 200
    assert released.json()["state"] == "DISSEMINATION_READY"
    assert product is not None
    assert product.metadata.status == ProductStatus.PUBLISHED
    event_types = [event["eventType"] for event in audit.json()["events"]]
    assert "product_released" in event_types
    assert "product_release_notification_failed" in event_types


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
