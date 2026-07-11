from typing import cast
from uuid import UUID

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from coeus.core.config import Settings
from coeus.domain.tickets import TicketRecord
from coeus.main import create_app
from rfi_search_helpers import login
from test_analyst_api import _approved_ticket, _assigned_ticket, _draft_payload


@pytest.mark.asyncio
async def test_assignment_audit_failure_rolls_back_ticket(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    analyst_user = app.state.access_services.repository.get_user_by_username("analyst@example.test")
    assert analyst_user is not None

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        ticket_id = await _approved_ticket(client)
        manager = await login(client, "rfa.manager@example.test")
        original = _stored_ticket(app, ticket_id)
        monkeypatch.setattr(app.state.analyst_workflow_service._audit_log, "record", _fail_audit)

        with pytest.raises(RuntimeError, match="audit unavailable"):
            await client.post(
                f"/api/v1/analyst/tasks/{ticket_id}/assign",
                headers={"X-CSRF-Token": str(manager["csrfToken"])},
                json={"analystUserIds": [str(analyst_user.user_id)]},
            )

    ticket = _stored_ticket(app, ticket_id)
    assert ticket.state == original.state
    assert ticket.analyst_assignments == original.analyst_assignments
    assert ticket.work_packages == original.work_packages
    assert ticket.timeline == original.timeline


@pytest.mark.asyncio
async def test_note_audit_failure_rolls_back_ticket(monkeypatch: pytest.MonkeyPatch) -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        ticket_id = await _assigned_ticket(client, app)
        analyst = await login(client, "analyst@example.test")
        original = _stored_ticket(app, ticket_id)
        monkeypatch.setattr(app.state.analyst_workflow_service._audit_log, "record", _fail_audit)

        with pytest.raises(RuntimeError, match="audit unavailable"):
            await client.post(
                f"/api/v1/analyst/tasks/{ticket_id}/notes",
                headers={"X-CSRF-Token": str(analyst["csrfToken"])},
                json={"body": "Checked the permitted assessment pack."},
            )

    ticket = _stored_ticket(app, ticket_id)
    assert ticket.analyst_notes == original.analyst_notes
    assert ticket.timeline == original.timeline


@pytest.mark.asyncio
async def test_product_link_audit_failure_rolls_back_ticket(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    product = next(
        item
        for item in app.state.store_services.repository.list_products()
        if item.metadata.title == "Assessment Draft Pack"
    )
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        ticket_id = await _assigned_ticket(client, app)
        analyst = await login(client, "analyst@example.test")
        original = _stored_ticket(app, ticket_id)
        monkeypatch.setattr(app.state.analyst_workflow_service._audit_log, "record", _fail_audit)

        with pytest.raises(RuntimeError, match="audit unavailable"):
            await client.post(
                f"/api/v1/analyst/tasks/{ticket_id}/products",
                headers={"X-CSRF-Token": str(analyst["csrfToken"])},
                json={"productId": str(product.product_id)},
            )

    ticket = _stored_ticket(app, ticket_id)
    assert ticket.linked_products == original.linked_products
    assert ticket.timeline == original.timeline


@pytest.mark.asyncio
async def test_work_package_audit_failure_rolls_back_ticket(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        ticket_id = await _assigned_ticket(client, app)
        analyst = await login(client, "analyst@example.test")
        original = _stored_ticket(app, ticket_id)
        package_id = original.work_packages[0].package_id
        monkeypatch.setattr(app.state.analyst_workflow_service._audit_log, "record", _fail_audit)

        with pytest.raises(RuntimeError, match="audit unavailable"):
            await client.patch(
                f"/api/v1/analyst/tasks/{ticket_id}/work-packages/{package_id}",
                headers={"X-CSRF-Token": str(analyst["csrfToken"])},
                json={"status": "complete"},
            )

    ticket = _stored_ticket(app, ticket_id)
    assert ticket.work_packages == original.work_packages
    assert ticket.timeline == original.timeline


@pytest.mark.asyncio
async def test_draft_audit_failure_rolls_back_ticket(monkeypatch: pytest.MonkeyPatch) -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        ticket_id = await _assigned_ticket(client, app)
        analyst = await login(client, "analyst@example.test")
        original = _stored_ticket(app, ticket_id)
        monkeypatch.setattr(app.state.analyst_workflow_service._audit_log, "record", _fail_audit)

        with pytest.raises(RuntimeError, match="audit unavailable"):
            await client.post(
                f"/api/v1/analyst/tasks/{ticket_id}/drafts",
                headers={"X-CSRF-Token": str(analyst["csrfToken"])},
                json=_draft_payload("Rollback draft"),
            )

    ticket = _stored_ticket(app, ticket_id)
    assert ticket.draft_products == original.draft_products
    assert ticket.timeline == original.timeline


@pytest.mark.asyncio
async def test_qc_submission_audit_failure_rolls_back_ticket(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        ticket_id = await _assigned_ticket(client, app)
        analyst = await login(client, "analyst@example.test")
        draft = await client.post(
            f"/api/v1/analyst/tasks/{ticket_id}/drafts",
            headers={"X-CSRF-Token": str(analyst["csrfToken"])},
            json=_draft_payload("Ready for QC"),
        )
        for package in draft.json()["workPackages"]:
            response = await client.patch(
                f"/api/v1/analyst/tasks/{ticket_id}/work-packages/{package['id']}",
                headers={"X-CSRF-Token": str(analyst["csrfToken"])},
                json={"status": "complete"},
            )
            assert response.status_code == 200
        original = _stored_ticket(app, ticket_id)
        monkeypatch.setattr(app.state.analyst_workflow_service._audit_log, "record", _fail_audit)

        with pytest.raises(RuntimeError, match="audit unavailable"):
            await client.post(
                f"/api/v1/analyst/tasks/{ticket_id}/submit",
                headers={"X-CSRF-Token": str(analyst["csrfToken"])},
            )

    ticket = _stored_ticket(app, ticket_id)
    assert ticket.state == original.state
    assert ticket.timeline == original.timeline


def _fail_audit(*_args: object, **_kwargs: object) -> None:
    raise RuntimeError("audit unavailable")


def _stored_ticket(app: FastAPI, ticket_id: str) -> TicketRecord:
    ticket = app.state.ticket_services.tickets._repository.get(UUID(ticket_id))
    assert ticket is not None
    return cast(TicketRecord, ticket)
