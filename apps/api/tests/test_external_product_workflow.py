import json
from hashlib import sha256
from io import BytesIO
from uuid import UUID

import pytest
from docx import Document
from httpx import ASGITransport, AsyncClient

from coeus.core.config import Settings
from coeus.main import create_app
from rfi_search_helpers import login
from routing_helpers import analyst_assignment_ticket, assignment_team_id
from test_qc_api import _approval_payload


@pytest.mark.asyncio
async def test_external_docx_survives_qc_release_byte_for_byte_and_is_proofed(
    tmp_path,
) -> None:
    app = create_app(
        Settings(
            environment="test",
            argon2_memory_cost=8_192,
            local_object_storage_path=str(tmp_path / "objects"),
        )
    )
    content = _docx(
        "MOCK DATA ONLY. The analyst definately confirmed synthetic movement in the test sector."
    )
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        ticket_id = await _assigned_ticket(client, app)
        analyst = await login(client, "analyst@example.test")
        acg_id = next(
            str(acg.acg_id)
            for acg in app.state.access_services.repository.list_acgs()
            if acg.code == "ACG-EU-CYBER"
        )
        uploaded = await client.post(
            f"/api/v1/analyst/tasks/{ticket_id}/submissions/upload",
            headers={"X-CSRF-Token": str(analyst["csrfToken"])},
            files={
                "asset": (
                    "assessment.docx",
                    content,
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                ),
                "metadata": (None, json.dumps(_metadata(acg_id)), "application/json"),
            },
        )
        assert uploaded.status_code == 201
        version = uploaded.json()["drafts"][-1]
        asset = version["assets"][0]
        workflow_preview = await client.get(
            f"/api/v1/workflow/products/{ticket_id}/versions/{version['id']}"
            f"/assets/{asset['id']}/preview"
        )
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
        manager = await login(client, "rfa.manager@example.test")
        manager_approved = await client.post(
            f"/api/v1/routing/{ticket_id}/manager-approval",
            headers={"X-CSRF-Token": str(manager["csrfToken"])},
        )
        qc = await login(client, "qc.manager@example.test")
        released = await client.post(
            f"/api/v1/qc/products/{ticket_id}/approve",
            headers={"X-CSRF-Token": str(qc["csrfToken"])},
            json=_approval_payload(acg_id),
        )
        product_id = released.json()["ingestedProduct"]["id"]
        await login(client, "user@example.test")
        product = await client.get(f"/api/v1/store/products/{product_id}")
        store_asset = product.json()["assets"][0]
        grant = await client.get(
            f"/api/v1/store/products/{product_id}/assets/{store_asset['id']}/access"
        )
        headers = {"X-Asset-Token": grant.json()["downloadToken"]}
        downloaded = await client.get(
            f"/api/v1/store/products/{product_id}/assets/{store_asset['id']}/download",
            headers=headers,
        )
        store_preview = await client.get(
            f"/api/v1/store/products/{product_id}/assets/{store_asset['id']}/preview",
            headers=headers,
        )

    assert asset["detectedMimeType"].endswith("wordprocessingml.document")
    assert asset["sha256"] == sha256(content).hexdigest()
    assert "definately confirmed" in workflow_preview.text
    assert submitted.json()["state"] == "MANAGER_APPROVAL"
    assert manager_approved.json()["state"] == "QC_REVIEW"
    stored = app.state.ticket_services.tickets._repository.get(UUID(ticket_id))
    assert stored is not None
    assert stored.manager_approved_manifest_hash == version["manifestHash"]
    findings = released.json()["agentPreflight"]["findings"]
    assert any(item["originalText"] == "definately" for item in findings)
    assert product.status_code == 200
    assert store_asset["sha256"] == sha256(content).hexdigest()
    assert downloaded.content == content
    assert "definately confirmed" in store_preview.text


async def _assigned_ticket(client: AsyncClient, app) -> str:
    ticket_id = await analyst_assignment_ticket(client)
    analyst = app.state.access_services.repository.get_user_by_username("analyst@example.test")
    assert analyst is not None
    manager = await login(client, "rfa.manager@example.test")
    assigned = await client.post(
        f"/api/v1/analyst/tasks/{ticket_id}/assign",
        headers={"X-CSRF-Token": str(manager["csrfToken"])},
        json={
            "analystUserIds": [str(analyst.user_id)],
            "teamId": await assignment_team_id(client),
        },
    )
    assert assigned.status_code == 200
    return ticket_id


def _metadata(acg_id: str) -> dict[str, object]:
    return {
        "title": "Synthetic external assessment",
        "summary": "MOCK DATA ONLY external analyst product.",
        "description": "MOCK DATA ONLY assessment prepared in Microsoft Word.",
        "productType": "assessment_report",
        "sourceType": "finished_assessment",
        "ownerTeam": "RFA",
        "areaOrRegion": "Test sector",
        "classificationLevel": 2,
        "releasability": ["MOCK"],
        "handlingCaveats": ["MOCK DATA ONLY"],
        "tags": ["synthetic", "external"],
        "acgIds": [acg_id],
        "timePeriodStart": "2026-07-01",
        "timePeriodEnd": "2026-07-31",
    }


def _docx(text: str) -> bytes:
    stream = BytesIO()
    document = Document()
    document.add_paragraph(text)
    document.save(stream)
    return stream.getvalue()
