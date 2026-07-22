import json
from pathlib import Path
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient

from coeus.core.config import Settings
from coeus.main import create_app
from rfi_search_helpers import login
from test_external_product_workflow import _assigned_ticket, _docx, _metadata


async def _submitted_rfa_product(
    client: AsyncClient, app, marker: str
) -> tuple[str, dict[str, object], UUID]:
    ticket_id = await _assigned_ticket(client, app)
    analyst = await login(client, "analyst@example.test")
    acg_id = next(
        acg.acg_id
        for acg in app.state.access_services.repository.list_acgs()
        if acg.code == "ACG-EU-CYBER"
    )
    uploaded = await client.post(
        f"/api/v1/analyst/tasks/{ticket_id}/submissions/upload",
        headers={"X-CSRF-Token": str(analyst["csrfToken"])},
        files={
            "asset": (
                "protected.docx",
                _docx(marker),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ),
            "metadata": (None, json.dumps(_metadata(str(acg_id))), "application/json"),
        },
    )
    assert uploaded.status_code == 201
    for package in uploaded.json()["workPackages"]:
        completed = await client.patch(
            f"/api/v1/analyst/tasks/{ticket_id}/work-packages/{package['id']}",
            headers={"X-CSRF-Token": str(analyst["csrfToken"])},
            json={"status": "complete"},
        )
        assert completed.status_code == 200
    submitted = await client.post(
        f"/api/v1/analyst/tasks/{ticket_id}/submit",
        headers={"X-CSRF-Token": str(analyst["csrfToken"])},
    )
    assert submitted.status_code == 200
    return ticket_id, uploaded.json()["drafts"][-1], acg_id


def _preview_path(ticket_id: str, version: dict[str, object]) -> str:
    asset = version["assets"][0]
    return (
        f"/api/v1/workflow/products/{ticket_id}/versions/{version['id']}"
        f"/assets/{asset['id']}/preview"
    )


@pytest.mark.asyncio
async def test_cross_route_manager_cannot_preview_rfa_submission(tmp_path: Path) -> None:
    app = create_app(
        Settings(
            environment="test",
            argon2_memory_cost=8_192,
            local_object_storage_path=str(tmp_path / "objects"),
        )
    )
    marker = "MOCK DATA ONLY. Route-bound protected draft."

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        ticket_id, version, _acg_id = await _submitted_rfa_product(client, app, marker)
        await login(client, "collection.manager@example.test")
        denied = await client.get(_preview_path(ticket_id, version))
        await login(client, "rfa.manager@example.test")
        allowed = await client.get(_preview_path(ticket_id, version))

    assert denied.status_code == 404
    assert marker not in denied.text
    assert allowed.status_code == 200
    assert marker[:-1] in allowed.text


@pytest.mark.asyncio
async def test_admin_cannot_use_preview_or_manager_routes_for_draft_content(
    tmp_path: Path,
) -> None:
    app = create_app(
        Settings(
            environment="test",
            argon2_memory_cost=8_192,
            local_object_storage_path=str(tmp_path / "objects"),
        )
    )
    marker = "MOCK DATA ONLY. Administrator-denied protected draft."

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        ticket_id, version, acg_id = await _submitted_rfa_product(client, app, marker)
        admin_user = app.state.access_services.repository.get_user_by_username("admin@example.test")
        assert admin_user is not None
        app.state.access_services.repository.remove_membership(acg_id, admin_user.user_id)
        admin = await login(client, "admin@example.test")
        preview = await client.get(_preview_path(ticket_id, version))
        queue = await client.get("/api/v1/routing/rfa/queue")
        work = await client.get(f"/api/v1/routing/{ticket_id}/manager-work")
        approval = await client.post(
            f"/api/v1/routing/{ticket_id}/manager-approval",
            headers={"X-CSRF-Token": str(admin["csrfToken"])},
        )

    assert preview.status_code == 404
    assert queue.status_code == 403
    assert work.status_code == 403
    assert approval.status_code == 403
    assert marker not in preview.text
    assert marker not in work.text


@pytest.mark.asyncio
async def test_named_qc_reviewer_can_preview_after_claim(tmp_path: Path) -> None:
    app = create_app(
        Settings(
            environment="test",
            argon2_memory_cost=8_192,
            local_object_storage_path=str(tmp_path / "objects"),
        )
    )
    marker = "MOCK DATA ONLY. Named QC reviewer protected draft."

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        ticket_id, version, _acg_id = await _submitted_rfa_product(client, app, marker)
        manager = await login(client, "rfa.manager@example.test")
        approved = await client.post(
            f"/api/v1/routing/{ticket_id}/manager-approval",
            headers={"X-CSRF-Token": str(manager["csrfToken"])},
        )
        assert approved.status_code == 200
        qc = await login(client, "qc.manager@example.test")
        claimed = await client.post(
            f"/api/v1/qc/products/{ticket_id}/claim",
            headers={"X-CSRF-Token": str(qc["csrfToken"])},
        )
        preview = await client.get(_preview_path(ticket_id, version))

    assert claimed.status_code == 200
    assert preview.status_code == 200
    assert marker[:-1] in preview.text
