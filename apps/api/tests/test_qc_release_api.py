"""QC-owned release hardening.

Ported from the retired manager-release suites: QC approval now performs the
final release, so the rollback, notification and access invariants attach to
the QC approve endpoint instead of a separate release endpoint.
"""

from uuid import UUID

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from coeus.core.config import Settings
from coeus.domain.access import ProductStatus
from coeus.domain.enums import TicketState
from coeus.domain.tickets import TicketRecord
from coeus.main import create_app
from rfi_search_helpers import login
from test_qc_api import _acg_id, _approval_payload, _submitted_qc_ticket


def _app() -> FastAPI:
    return create_app(Settings(environment="test", argon2_memory_cost=8_192))


async def _approve(client: AsyncClient, ticket_id: str, acg_id: str, **overrides: object):
    qc_manager = await login(client, "qc.manager@example.test")
    payload = _approval_payload(acg_id)
    payload.update(overrides)
    return await client.post(
        f"/api/v1/qc/products/{ticket_id}/approve",
        headers={"X-CSRF-Token": str(qc_manager["csrfToken"])},
        json=payload,
    )


def _stored_ticket(app: FastAPI, ticket_id: str) -> TicketRecord:
    ticket = app.state.ticket_services.tickets._repository.get(UUID(ticket_id))
    assert ticket is not None
    return ticket


@pytest.mark.asyncio
async def test_release_audit_events_and_email_are_recorded() -> None:
    app = _app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        ticket_id = await _submitted_qc_ticket(client, app, "Release Arctic product")
        released = await _approve(client, ticket_id, _acg_id(app, "ACG-EU-CYBER"))
        await login(client, "admin@example.test")
        audit = await client.get("/api/v1/audit")

    assert released.status_code == 200
    assert released.json()["state"] == "DISSEMINATION_READY"
    event_types = [event["eventType"] for event in audit.json()["events"]]
    assert "product_released" in event_types
    assert "email_recorded" in event_types


@pytest.mark.asyncio
async def test_unreadable_product_fails_approval_without_an_orphan() -> None:
    app = _app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        ticket_id = await _submitted_qc_ticket(client, app, "Too restricted release product")
        # Classification 4 puts the product beyond the requester's clearance.
        failed = await _approve(
            client, ticket_id, _acg_id(app, "ACG-EU-CYBER"), classificationLevel=4
        )

    ticket = _stored_ticket(app, ticket_id)
    assert failed.status_code == 404
    assert failed.json()["error"]["code"] == "product_not_found"
    assert ticket.state == TicketState.QC_REVIEW
    assert ticket.disseminations == ()
    assert ticket.product_index_records == ()
    # The ingested product was discarded, not left as an orphaned draft.
    assert all(
        product.metadata.title != "Too restricted release product"
        for product in app.state.store_services.repository.list_products()
    )


@pytest.mark.asyncio
async def test_inactive_requester_fails_approval_without_an_orphan() -> None:
    app = _app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        ticket_id = await _submitted_qc_ticket(client, app, "Inactive requester product")
        requester = app.state.access_services.repository.get_user_by_username("user@example.test")
        assert requester is not None
        admin = await login(client, "admin@example.test")
        disabled = await client.put(
            f"/api/v1/admin/users/{requester.user_id}/status",
            headers={"X-CSRF-Token": str(admin["csrfToken"])},
            json={"isActive": False},
        )
        assert disabled.status_code == 200
        failed = await _approve(client, ticket_id, _acg_id(app, "ACG-EU-CYBER"))

    ticket = _stored_ticket(app, ticket_id)
    assert failed.status_code == 409
    assert failed.json()["error"]["code"] == "requester_not_active"
    assert ticket.state == TicketState.QC_REVIEW
    assert ticket.product_index_records == ()


@pytest.mark.asyncio
async def test_ticket_update_failure_rolls_back_the_published_product(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        ticket_id = await _submitted_qc_ticket(client, app, "Rollback release product")
        tickets = app.state.ticket_services.tickets
        original = tickets.save_system_update

        def fail_save(_ticket: TicketRecord) -> TicketRecord:
            raise RuntimeError("simulated release persistence failure")

        monkeypatch.setattr(tickets, "save_system_update", fail_save)
        with pytest.raises(RuntimeError, match="simulated release persistence failure"):
            await _approve(client, ticket_id, _acg_id(app, "ACG-EU-CYBER"))
        monkeypatch.setattr(tickets, "save_system_update", original)

        await login(client, "user@example.test")
        notifications = await client.get("/api/v1/notifications")
        search = await client.get("/api/v1/store/products?query=Rollback%20release")

    ticket = _stored_ticket(app, ticket_id)
    assert ticket.state == TicketState.QC_REVIEW
    assert ticket.disseminations == ()
    assert ticket.product_index_records == ()
    assert notifications.json()["unread"] == 0
    assert search.json()["products"] == []


@pytest.mark.asyncio
async def test_audit_failure_rolls_back_ticket_and_product(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        ticket_id = await _submitted_qc_ticket(client, app, "Audit rollback product")
        audit_log = app.state.quality_control_service._audit_log
        original_record = audit_log.record

        def fail_audit(*_args: object, **_kwargs: object) -> None:
            raise RuntimeError("release audit unavailable")

        monkeypatch.setattr(audit_log, "record", fail_audit)
        with pytest.raises(RuntimeError, match="release audit unavailable"):
            await _approve(client, ticket_id, _acg_id(app, "ACG-EU-CYBER"))
        monkeypatch.setattr(audit_log, "record", original_record)

        await login(client, "user@example.test")
        notifications = await client.get("/api/v1/notifications")
        search = await client.get("/api/v1/store/products?query=Audit%20rollback")

    ticket = _stored_ticket(app, ticket_id)
    assert ticket.state == TicketState.QC_REVIEW
    assert ticket.disseminations == ()
    assert ticket.feedback_requests == ()
    assert notifications.json()["unread"] == 0
    assert search.json()["products"] == []


@pytest.mark.asyncio
async def test_release_succeeds_when_notification_side_effect_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        ticket_id = await _submitted_qc_ticket(client, app, "Notify failure product")

        def fail_notify(*_args: object, **_kwargs: object) -> None:
            raise RuntimeError("notification backend unavailable")

        monkeypatch.setattr(app.state.notification_service, "notify", fail_notify)
        released = await _approve(client, ticket_id, _acg_id(app, "ACG-EU-CYBER"))
        await login(client, "admin@example.test")
        audit = await client.get("/api/v1/audit")

    ticket = _stored_ticket(app, ticket_id)
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
async def test_release_survives_notification_failure_audit_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        ticket_id = await _submitted_qc_ticket(client, app, "Double failure product")

        def fail_notify(*_args: object, **_kwargs: object) -> None:
            raise RuntimeError("notification backend unavailable")

        monkeypatch.setattr(app.state.notification_service, "notify", fail_notify)
        audit_log = app.state.quality_control_service._audit_log
        original_record = audit_log.record

        def fail_notification_failure_audit(
            event_type: str,
            actor_user_id: str | None = None,
            metadata: dict[str, str] | None = None,
        ) -> None:
            if event_type == "product_release_notification_failed":
                raise RuntimeError("notification failure audit unavailable")
            original_record(event_type, actor_user_id, metadata)

        monkeypatch.setattr(audit_log, "record", fail_notification_failure_audit)
        released = await _approve(client, ticket_id, _acg_id(app, "ACG-EU-CYBER"))

    ticket = _stored_ticket(app, ticket_id)
    product = app.state.store_services.repository.get_product(
        ticket.product_index_records[-1].product_id
    )
    assert released.status_code == 200
    assert released.json()["state"] == "DISSEMINATION_READY"
    assert product is not None
    assert product.metadata.status == ProductStatus.PUBLISHED
