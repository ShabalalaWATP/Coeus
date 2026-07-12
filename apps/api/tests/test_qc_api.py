from dataclasses import replace
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from coeus.core.config import Settings
from coeus.core.errors import AppError
from coeus.main import create_app
from coeus.services.qc_records import preview_kind
from coeus.services.quality_control import QcApprovalInput, ReleaseCheckService
from rfi_search_helpers import login
from routing_helpers import analyst_assignment_ticket, assignment_team_id


@pytest.mark.asyncio
async def test_qc_approval_releases_the_product_to_the_customer() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    acg_id = _acg_id(app, "ACG-EU-CYBER")
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        ticket_id = await _submitted_qc_ticket(client, app, "Approved Arctic QC product")
        qc_manager = await login(client, "qc.manager@example.test")
        queue = await client.get("/api/v1/qc/queue")
        approved = await client.post(
            f"/api/v1/qc/products/{ticket_id}/approve",
            headers={"X-CSRF-Token": str(qc_manager["csrfToken"])},
            json=_approval_payload(acg_id),
        )
        await login(client, "user@example.test")
        search = await client.get("/api/v1/store/products?query=Approved%20Arctic")
        notifications = await client.get("/api/v1/notifications")

    assert queue.status_code == 200
    assert queue.json()["products"][0]["ticketId"] == ticket_id
    assert queue.json()["products"][0]["latestDraft"]["title"] == "Approved Arctic QC product"
    assert len(queue.json()["products"][0]["checklistKeys"]) == 9
    assert approved.status_code == 200
    body = approved.json()
    assert body["state"] == "DISSEMINATION_READY"
    assert body["decisions"][0]["status"] == "approved"
    assert [record["status"] for record in body["indexRecords"]] == ["queued", "indexed"]
    assert body["ingestedProduct"]["title"] == "Approved Arctic QC product"
    assert len(body["disseminations"]) == 1
    assert len(body["feedbackRequests"]) == 1
    # QC now performs the final release: the customer can find the product.
    assert body["ingestedProduct"]["id"] in {product["id"] for product in search.json()["products"]}
    assert notifications.json()["unread"] == 1
    assert notifications.json()["notifications"][0]["kind"] == "product_released"


@pytest.mark.asyncio
async def test_qc_rejects_to_rework_and_analyst_can_resubmit() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        ticket_id = await _submitted_qc_ticket(client, app, "Rework Arctic product")
        qc_manager = await login(client, "qc.manager@example.test")
        rejected = await client.post(
            f"/api/v1/qc/products/{ticket_id}/reject",
            headers={"X-CSRF-Token": str(qc_manager["csrfToken"])},
            json={"reason": "Sources need clearer mock provenance."},
        )
        analyst = await login(client, "analyst@example.test")
        tasks = await client.get("/api/v1/analyst/tasks")
        unchanged = await client.post(
            f"/api/v1/analyst/tasks/{ticket_id}/submit",
            headers={"X-CSRF-Token": str(analyst["csrfToken"])},
        )
        revised = await client.post(
            f"/api/v1/analyst/tasks/{ticket_id}/drafts",
            headers={"X-CSRF-Token": str(analyst["csrfToken"])},
            json=_draft_payload("Revised Arctic product"),
        )
        resubmitted = await client.post(
            f"/api/v1/analyst/tasks/{ticket_id}/submit",
            headers={"X-CSRF-Token": str(analyst["csrfToken"])},
        )

    assert rejected.status_code == 200
    assert rejected.json()["state"] == "REWORK_REQUIRED"
    assert rejected.json()["decisions"][0]["status"] == "rejected"
    assert tasks.status_code == 200
    assert tasks.json()["tasks"][0]["state"] == "REWORK_REQUIRED"
    assert unchanged.status_code == 409
    assert unchanged.json()["error"]["code"] == "revised_draft_required"
    assert revised.status_code == 200
    assert revised.json()["drafts"][-1]["title"] == "Revised Arctic product"
    assert resubmitted.status_code == 200
    assert resubmitted.json()["state"] == "QC_REVIEW"


@pytest.mark.asyncio
async def test_qc_blocks_incomplete_checklist_and_self_approval() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    acg_id = _acg_id(app, "ACG-EU-CYBER")
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        ticket_id = await _submitted_qc_ticket(client, app, "Duty separation product")
        analyst = await login(client, "analyst@example.test")
        analyst_approval = await client.post(
            f"/api/v1/qc/products/{ticket_id}/approve",
            headers={"X-CSRF-Token": str(analyst["csrfToken"])},
            json=_approval_payload(acg_id),
        )
        qc_manager = await login(client, "qc.manager@example.test")
        incomplete = _approval_payload(acg_id)
        incomplete["checklist"]["sources_are_sufficient"] = False
        incomplete_approval = await client.post(
            f"/api/v1/qc/products/{ticket_id}/approve",
            headers={"X-CSRF-Token": str(qc_manager["csrfToken"])},
            json=incomplete,
        )
        _make_qc_manager_latest_drafter(app, ticket_id)
        self_approval = await client.post(
            f"/api/v1/qc/products/{ticket_id}/approve",
            headers={"X-CSRF-Token": str(qc_manager["csrfToken"])},
            json=_approval_payload(acg_id),
        )

    assert analyst_approval.status_code == 403
    assert analyst_approval.json()["error"]["code"] == "forbidden"
    assert incomplete_approval.status_code == 409
    assert incomplete_approval.json()["error"]["code"] == "qc_checklist_incomplete"
    assert self_approval.status_code == 403
    assert self_approval.json()["error"]["code"] == "separation_of_duties"


@pytest.mark.asyncio
async def test_qc_approval_rejects_acg_outside_actor_scope() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    collection_acg_id = _acg_id(app, "ACG-BRAVO-COLLECTION")

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        ticket_id = await _submitted_qc_ticket(client, app, "Unauthorised ACG product")
        qc_manager = await login(client, "qc.manager@example.test")
        approved = await client.post(
            f"/api/v1/qc/products/{ticket_id}/approve",
            headers={"X-CSRF-Token": str(qc_manager["csrfToken"])},
            json=_approval_payload(collection_acg_id),
        )

    assert approved.status_code == 403
    assert approved.json()["error"]["code"] == "acg_not_authorised"


@pytest.mark.asyncio
async def test_qc_ingestion_uses_only_qc_confirmed_access_metadata() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    acg_id = _acg_id(app, "ACG-EU-CYBER")

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        ticket_id = await _submitted_qc_ticket(client, app, "Standalone QC product")
        qc_manager = await login(client, "qc.manager@example.test")
        approved = await client.post(
            f"/api/v1/qc/products/{ticket_id}/approve",
            headers={"X-CSRF-Token": str(qc_manager["csrfToken"])},
            json=_approval_payload(acg_id),
        )

    assert approved.status_code == 200
    product_id = approved.json()["ingestedProduct"]["id"]
    product = app.state.store_services.repository.get_product(UUID(product_id))
    assert product is not None
    assert approved.json()["ingestedProduct"]["acgIds"] == [acg_id]
    assert product.metadata.acg_ids == frozenset({UUID(acg_id)})


def test_release_checks_validate_metadata_and_preview_kinds() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    checks = ReleaseCheckService(app.state.access_services.repository)
    acg_id = UUID(_acg_id(app, "ACG-ALPHA-REGIONAL"))
    base = QcApprovalInput(
        checklist={},
        classification_level=2,
        releasability=("MOCK",),
        handling_caveats=("MOCK DATA ONLY",),
        acg_ids=frozenset({acg_id}),
        reason="Complete.",
    )

    with pytest.raises(AppError, match="Releasability"):
        checks.validate_release_metadata(replace(base, releasability=()))
    with pytest.raises(AppError, match="Handling"):
        checks.validate_release_metadata(replace(base, handling_caveats=()))
    with pytest.raises(AppError, match="ACG"):
        checks.validate_release_metadata(replace(base, acg_ids=frozenset()))
    with pytest.raises(AppError, match="active ACGs"):
        checks.validate_release_metadata(replace(base, acg_ids=frozenset({uuid4()})))

    assert preview_kind("image/png", "png") == "image"
    assert preview_kind("application/geo+json", "geojson") == "geojson"
    assert preview_kind("text/plain", "text") == "text_metadata"


async def _submitted_qc_ticket(client: AsyncClient, app: FastAPI, draft_title: str) -> str:
    """Walk an assigned ticket through drafting, manager approval and into QC."""
    ticket_id = await _assigned_ticket(client, app)
    analyst = await login(client, "analyst@example.test")
    draft = await client.post(
        f"/api/v1/analyst/tasks/{ticket_id}/drafts",
        headers={"X-CSRF-Token": str(analyst["csrfToken"])},
        json=_draft_payload(draft_title),
    )
    assert draft.status_code == 200
    for package in draft.json()["workPackages"]:
        updated = await client.patch(
            f"/api/v1/analyst/tasks/{ticket_id}/work-packages/{package['id']}",
            headers={"X-CSRF-Token": str(analyst["csrfToken"])},
            json={"status": "complete"},
        )
        assert updated.status_code == 200
    submitted = await client.post(
        f"/api/v1/analyst/tasks/{ticket_id}/submit",
        headers={"X-CSRF-Token": str(analyst["csrfToken"])},
    )
    assert submitted.status_code == 200
    assert submitted.json()["state"] == "MANAGER_APPROVAL"
    manager = await login(client, "rfa.manager@example.test")
    approved = await client.post(
        f"/api/v1/routing/{ticket_id}/manager-approval",
        headers={"X-CSRF-Token": str(manager["csrfToken"])},
    )
    assert approved.status_code == 200
    assert approved.json()["state"] == "QC_REVIEW"
    return ticket_id


async def _assigned_ticket(client: AsyncClient, app: FastAPI) -> str:
    ticket_id = await _approved_ticket(client)
    analyst_user = app.state.access_services.repository.get_user_by_username("analyst@example.test")
    assert analyst_user is not None
    manager = await login(client, "rfa.manager@example.test")
    team_id = await assignment_team_id(client)
    assigned = await client.post(
        f"/api/v1/analyst/tasks/{ticket_id}/assign",
        headers={"X-CSRF-Token": str(manager["csrfToken"])},
        json={"analystUserIds": [str(analyst_user.user_id)], "teamId": team_id},
    )
    assert assigned.status_code == 200
    return ticket_id


async def _approved_ticket(client: AsyncClient) -> str:
    return await analyst_assignment_ticket(client)


def _approval_payload(acg_id: str) -> dict[str, Any]:
    return {
        "checklist": {
            "answers_customer_question": True,
            "sources_are_sufficient": True,
            "metadata_complete": True,
            "classification_checked": True,
            "releasability_checked": True,
            "acg_assignment_checked": True,
            "format_correct": True,
            "handling_caveats_applied": True,
            "manager_comments_resolved": True,
        },
        "classificationLevel": 2,
        "releasability": ["MOCK"],
        "handlingCaveats": ["MOCK DATA ONLY"],
        "acgIds": [acg_id],
        "reason": "QC checklist complete.",
    }


def _draft_payload(title: str) -> dict[str, Any]:
    return {
        "title": title,
        "summary": "MOCK DATA ONLY analyst product draft.",
        "productType": "finished_output",
        "content": "MOCK DATA ONLY. Assessment content prepared for QC review.",
        "assets": [
            {
                "name": "assessment-draft.pdf",
                "assetType": "pdf",
                "mimeType": "application/pdf",
                "sizeBytes": 512,
                "sha256": "d" * 64,
            }
        ],
    }


def _acg_id(app: FastAPI, code: str) -> str:
    for acg in app.state.access_services.repository.list_acgs():
        if acg.code == code:
            return str(acg.acg_id)
    raise AssertionError(f"Missing seed ACG {code}")


def _make_qc_manager_latest_drafter(app: FastAPI, ticket_id: str) -> None:
    manager = app.state.access_services.repository.get_user_by_username("qc.manager@example.test")
    assert manager is not None
    repository = app.state.ticket_services.tickets._repository
    ticket = repository.get(UUID(ticket_id))
    assert ticket is not None
    draft = replace(ticket.draft_products[-1], created_by_user_id=manager.user_id)
    repository.save(replace(ticket, draft_products=(*ticket.draft_products[:-1], draft)))
