from dataclasses import replace
from pathlib import Path
from typing import cast
from uuid import UUID

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from coeus.core.config import Settings
from coeus.domain.enums import TicketState
from coeus.domain.store import StoreProduct
from coeus.domain.tickets import TicketRecord
from coeus.main import create_app
from coeus.services.qc_ingestion import iso_date_or_none
from rfi_search_helpers import login
from test_qc_api import _acg_id, _approval_payload, _submitted_qc_ticket


def _app(tmp_path: Path) -> FastAPI:
    return create_app(
        Settings(
            environment="test",
            argon2_memory_cost=8_192,
            local_object_storage_path=str(tmp_path / "objects"),
        )
    )


def test_iso_date_or_none_accepts_dates_and_drops_free_text() -> None:
    assert iso_date_or_none(None) is None
    assert iso_date_or_none("2026-08-01") == "2026-08-01"
    assert iso_date_or_none("next week") is None
    assert iso_date_or_none("2026-13-40") is None


@pytest.mark.asyncio
async def test_qc_approval_sanitises_free_text_time_periods(tmp_path: Path) -> None:
    app = _app(tmp_path)
    acg_id = _acg_id(app, "ACG-EU-CYBER")
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        ticket_id = await _submitted_qc_ticket(client, app, "Sanitised period product")
        repository = app.state.ticket_services.tickets._repository
        ticket = repository.get(UUID(ticket_id))
        assert ticket is not None
        repository.save(
            replace(
                ticket,
                intake=replace(
                    ticket.intake,
                    time_period_start="next week",
                    time_period_end="2026-08-01",
                ),
            )
        )
        qc_manager = await login(client, "qc.manager@example.test")
        approved = await client.post(
            f"/api/v1/qc/products/{ticket_id}/approve",
            headers={"X-CSRF-Token": str(qc_manager["csrfToken"])},
            json=_approval_payload(acg_id),
        )

    assert approved.status_code == 200
    product_id = UUID(approved.json()["ingestedProduct"]["id"])
    product = app.state.store_services.repository.get_product(product_id)
    assert product is not None
    assert product.metadata.time_period_start is None
    assert product.metadata.time_period_end == "2026-08-01"


@pytest.mark.asyncio
async def test_qc_ingestion_writes_downloadable_bytes_immediately(tmp_path: Path) -> None:
    app = _app(tmp_path)
    acg_id = _acg_id(app, "ACG-EU-CYBER")
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        ticket_id = await _submitted_qc_ticket(client, app, "Downloadable QC product")
        qc_manager = await login(client, "qc.manager@example.test")
        approved = await client.post(
            f"/api/v1/qc/products/{ticket_id}/approve",
            headers={"X-CSRF-Token": str(qc_manager["csrfToken"])},
            json=_approval_payload(acg_id),
        )

    assert approved.status_code == 200
    product_id = UUID(approved.json()["ingestedProduct"]["id"])
    product = app.state.store_services.repository.get_product(product_id)
    assert product is not None
    for asset in product.assets:
        # The object key embeds the store asset's own identity and the bytes
        # exist without any restart or reseed step.
        assert str(asset.asset_id) in asset.object_key
        assert app.state.object_storage.exists(asset.object_key)
        content = app.state.object_storage.path_for(asset.object_key).read_bytes()
        assert product.reference.encode() in content
        assert asset.name.encode() in content
        assert asset.sha256.encode() in content


@pytest.mark.asyncio
async def test_failed_ticket_update_rolls_back_ingested_product(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app = _app(tmp_path)
    acg_id = _acg_id(app, "ACG-EU-CYBER")
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        ticket_id = await _submitted_qc_ticket(client, app, "Rollback QC product")
        qc_manager = await login(client, "qc.manager@example.test")
        tickets = app.state.ticket_services.tickets
        original = tickets.save_system_update

        def boom(_ticket: TicketRecord) -> TicketRecord:
            raise RuntimeError("simulated persistence failure")

        monkeypatch.setattr(tickets, "save_system_update", boom)
        # The test transport re-raises server-side exceptions directly.
        with pytest.raises(RuntimeError, match="simulated persistence failure"):
            await client.post(
                f"/api/v1/qc/products/{ticket_id}/approve",
                headers={"X-CSRF-Token": str(qc_manager["csrfToken"])},
                json=_approval_payload(acg_id),
            )
        monkeypatch.setattr(tickets, "save_system_update", original)
        orphaned = [
            product
            for product in app.state.store_services.repository.list_products()
            if "qc-approved" in product.metadata.tags
        ]
        orphaned_objects = list((tmp_path / "objects" / "store" / "qc" / ticket_id).rglob("*"))
        retried = await client.post(
            f"/api/v1/qc/products/{ticket_id}/approve",
            headers={"X-CSRF-Token": str(qc_manager["csrfToken"])},
            json=_approval_payload(acg_id),
        )

    assert orphaned == []
    assert orphaned_objects == []
    assert retried.status_code == 200
    assert retried.json()["state"] == "MANAGER_RELEASE"


@pytest.mark.asyncio
async def test_failed_indexing_rolls_back_ingested_product(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app = _app(tmp_path)
    acg_id = _acg_id(app, "ACG-EU-CYBER")
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        ticket_id = await _submitted_qc_ticket(client, app, "Index rollback QC product")
        qc_manager = await login(client, "qc.manager@example.test")
        indexing = app.state.quality_control_service._indexing
        original = indexing.index_product

        def boom(_ticket: TicketRecord, _product: StoreProduct) -> None:
            raise RuntimeError("simulated indexing failure")

        monkeypatch.setattr(indexing, "index_product", boom)
        with pytest.raises(RuntimeError, match="simulated indexing failure"):
            await client.post(
                f"/api/v1/qc/products/{ticket_id}/approve",
                headers={"X-CSRF-Token": str(qc_manager["csrfToken"])},
                json=_approval_payload(acg_id),
            )
        monkeypatch.setattr(indexing, "index_product", original)
        orphaned = [
            product
            for product in app.state.store_services.repository.list_products()
            if "qc-approved" in product.metadata.tags
        ]
        orphaned_objects = list((tmp_path / "objects" / "store" / "qc" / ticket_id).rglob("*"))
        retried = await client.post(
            f"/api/v1/qc/products/{ticket_id}/approve",
            headers={"X-CSRF-Token": str(qc_manager["csrfToken"])},
            json=_approval_payload(acg_id),
        )

    assert orphaned == []
    assert orphaned_objects == []
    assert retried.status_code == 200
    assert retried.json()["state"] == "MANAGER_RELEASE"


@pytest.mark.asyncio
async def test_failed_qc_approval_audit_rolls_back_ticket_and_product(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app = _app(tmp_path)
    acg_id = _acg_id(app, "ACG-EU-CYBER")
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        ticket_id = await _submitted_qc_ticket(client, app, "Audit rollback QC product")
        qc_manager = await login(client, "qc.manager@example.test")
        monkeypatch.setattr(app.state.quality_control_service._audit_log, "record", _fail_audit)

        with pytest.raises(RuntimeError, match="audit unavailable"):
            await client.post(
                f"/api/v1/qc/products/{ticket_id}/approve",
                headers={"X-CSRF-Token": str(qc_manager["csrfToken"])},
                json=_approval_payload(acg_id),
            )

    ticket = _stored_ticket(app, ticket_id)
    orphaned = [
        product
        for product in app.state.store_services.repository.list_products()
        if "qc-approved" in product.metadata.tags
    ]
    orphaned_objects = list((tmp_path / "objects" / "store" / "qc" / ticket_id).rglob("*"))

    assert ticket.state == TicketState.QC_REVIEW
    assert ticket.qc_decisions == ()
    assert ticket.product_index_records == ()
    assert orphaned == []
    assert orphaned_objects == []


@pytest.mark.asyncio
async def test_failed_qc_rejection_audit_rolls_back_ticket(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app = _app(tmp_path)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        ticket_id = await _submitted_qc_ticket(client, app, "Rejection audit rollback product")
        qc_manager = await login(client, "qc.manager@example.test")
        original = _stored_ticket(app, ticket_id)
        monkeypatch.setattr(app.state.quality_control_service._audit_log, "record", _fail_audit)

        with pytest.raises(RuntimeError, match="audit unavailable"):
            await client.post(
                f"/api/v1/qc/products/{ticket_id}/reject",
                headers={"X-CSRF-Token": str(qc_manager["csrfToken"])},
                json={"reason": "Audit rollback should keep QC pending."},
            )

    ticket = _stored_ticket(app, ticket_id)

    assert ticket.state == TicketState.QC_REVIEW
    assert ticket.qc_decisions == original.qc_decisions
    assert ticket.timeline == original.timeline


def _fail_audit(*_args: object, **_kwargs: object) -> None:
    raise RuntimeError("audit unavailable")


def _stored_ticket(app: FastAPI, ticket_id: str) -> TicketRecord:
    ticket = app.state.ticket_services.tickets._repository.get(UUID(ticket_id))
    assert ticket is not None
    return cast(TicketRecord, ticket)
