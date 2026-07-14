from typing import Any
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from coeus.core.config import Settings
from coeus.main import create_app
from rfi_search_helpers import login
from routing_helpers import analyst_assignment_ticket
from store_api_helpers import product_payload


def _rfa_team(app: FastAPI):
    return next(
        team.team_id for team in app.state.team_repository.list_teams() if team.kind.value == "rfa"
    )


async def _published_for_analyst(client: AsyncClient, app: FastAPI) -> dict[str, Any]:
    analyst = app.state.access_services.repository.get_user_by_username("analyst@example.test")
    assert analyst is not None
    acg_id = next(
        iter(app.state.access_services.repository.active_acg_ids_for_user(analyst.user_id))
    )
    admin = await login(client, "admin@example.test")
    response = await client.post(
        "/api/v1/store/products",
        headers={"X-CSRF-Token": str(admin["csrfToken"])},
        json={
            **product_payload(str(acg_id)),
            "title": "Mock Published Analyst Source",
            "status": "published",
        },
    )
    assert response.status_code == 201
    return response.json()


@pytest.mark.asyncio
async def test_manager_assigns_analyst_and_workbench_lists_assigned_tasks_only() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    analyst_user = app.state.access_services.repository.get_user_by_username("analyst@example.test")
    assert analyst_user is not None
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        ticket_id = await _approved_ticket(client)
        manager = await login(client, "rfa.manager@example.test")
        team_id = next(
            team.team_id
            for team in app.state.team_repository.list_teams()
            if team.kind.value == "rfa"
        )
        candidates = await client.get(f"/api/v1/analyst/candidates?route=rfa&teamId={team_id}")
        assigned = await client.post(
            f"/api/v1/analyst/tasks/{ticket_id}/assign",
            headers={"X-CSRF-Token": str(manager["csrfToken"])},
            json={
                "analystUserIds": [str(analyst_user.user_id)],
                "teamId": str(team_id),
                "workPackages": ["Review permitted products", "Draft assessment"],
            },
        )
        analyst = await login(client, "analyst@example.test")
        tasks = await client.get("/api/v1/analyst/tasks")

    assert candidates.status_code == 200
    assert candidates.json()["analysts"][0]["username"] == "analyst@example.test"
    candidate_names = {candidate["displayName"] for candidate in candidates.json()["analysts"]}
    assert {"Nathan Patterson", "Ben Doak", "Che Adams"}.issubset(candidate_names)
    assert assigned.status_code == 200
    assert assigned.json()["state"] == "ANALYST_IN_PROGRESS"
    assert assigned.json()["assignments"][0]["analystUserId"] == str(analyst_user.user_id)
    assert assigned.json()["assignments"][0]["teamName"] == "RFA Assessment Team"
    assert [package["title"] for package in assigned.json()["workPackages"]] == [
        "Review permitted products",
        "Draft assessment",
    ]
    assert analyst["user"]["username"] == "analyst@example.test"
    assert tasks.status_code == 200
    assert [task["ticketId"] for task in tasks.json()["tasks"]] == [ticket_id]
    assert tasks.json()["tasks"][0]["assignments"][0]["teamName"] == "RFA Assessment Team"
    assert tasks.json()["tasks"][0]["managerNotes"] == [
        "Collection not required; approved for RFA analyst assignment."
    ]


@pytest.mark.asyncio
async def test_analyst_adds_note_and_links_only_permitted_store_products() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    denied = next(
        product
        for product in app.state.store_services.repository.list_products()
        if product.metadata.title == "Collection Sensor Summary"
    )
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        ticket_id = await _assigned_ticket(client, app)
        permitted = await _published_for_analyst(client, app)
        analyst = await login(client, "analyst@example.test")
        note = await client.post(
            f"/api/v1/analyst/tasks/{ticket_id}/notes",
            headers={"X-CSRF-Token": str(analyst["csrfToken"])},
            json={"body": "Checked the permitted assessment pack."},
        )
        linked = await client.post(
            f"/api/v1/analyst/tasks/{ticket_id}/products",
            headers={"X-CSRF-Token": str(analyst["csrfToken"])},
            json={"productId": permitted["id"]},
        )
        denied_link = await client.post(
            f"/api/v1/analyst/tasks/{ticket_id}/products",
            headers={"X-CSRF-Token": str(analyst["csrfToken"])},
            json={"productId": str(denied.product_id)},
        )

    assert note.status_code == 200
    assert note.json()["notes"][0]["body"] == "Checked the permitted assessment pack."
    assert linked.status_code == 200
    assert linked.json()["linkedProducts"][0]["title"] == "Mock Published Analyst Source"
    assert denied_link.status_code == 404
    assert denied_link.json()["error"]["code"] == "product_not_found"


@pytest.mark.asyncio
async def test_draft_product_versions_and_submit_to_manager_transition() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        ticket_id = await _assigned_ticket(client, app)
        analyst = await login(client, "analyst@example.test")
        first_draft = await client.post(
            f"/api/v1/analyst/tasks/{ticket_id}/drafts",
            headers={"X-CSRF-Token": str(analyst["csrfToken"])},
            json=_draft_payload("Arctic assessment draft"),
        )
        blocked = await client.post(
            f"/api/v1/analyst/tasks/{ticket_id}/submit",
            headers={"X-CSRF-Token": str(analyst["csrfToken"])},
        )
        task = first_draft.json()
        for package in task["workPackages"]:
            task = (
                await client.patch(
                    f"/api/v1/analyst/tasks/{ticket_id}/work-packages/{package['id']}",
                    headers={"X-CSRF-Token": str(analyst["csrfToken"])},
                    json={"status": "complete"},
                )
            ).json()
        second_draft = await client.post(
            f"/api/v1/analyst/tasks/{ticket_id}/drafts",
            headers={"X-CSRF-Token": str(analyst["csrfToken"])},
            json=_draft_payload("Arctic assessment final draft"),
        )
        submitted = await client.post(
            f"/api/v1/analyst/tasks/{ticket_id}/submit",
            headers={"X-CSRF-Token": str(analyst["csrfToken"])},
        )
        admin = await login(client, "admin@example.test")
        audit = await client.get("/api/v1/audit")

    assert first_draft.status_code == 200
    assert first_draft.json()["drafts"][0]["versionNumber"] == 1
    assert first_draft.json()["drafts"][0]["assets"][0]["name"] == "assessment-draft.pdf"
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "work_packages_incomplete"
    assert all(package["status"] == "complete" for package in task["workPackages"])
    assert second_draft.status_code == 200
    assert [draft["versionNumber"] for draft in second_draft.json()["drafts"]] == [1, 2]
    assert submitted.status_code == 200
    assert submitted.json()["state"] == "MANAGER_APPROVAL"
    audit_events = [event["eventType"] for event in audit.json()["events"]]
    assert "work_package_updated" in audit_events
    assert "submitted_to_manager" in audit_events
    assert admin["user"]["username"] == "admin@example.test"


@pytest.mark.asyncio
async def test_non_manager_cannot_assign_and_unassigned_analyst_cannot_open_task() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    analyst_user = app.state.access_services.repository.get_user_by_username("analyst@example.test")
    assert analyst_user is not None
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        ticket_id = await _approved_ticket(client)
        customer = await login(client, "user@example.test")
        forbidden = await client.post(
            f"/api/v1/analyst/tasks/{ticket_id}/assign",
            headers={"X-CSRF-Token": str(customer["csrfToken"])},
            json={"analystUserIds": [str(analyst_user.user_id)], "teamId": str(_rfa_team(app))},
        )
        await login(client, "analyst@example.test")
        missing_task = await client.get(f"/api/v1/analyst/tasks/{ticket_id}")

    assert forbidden.status_code == 403
    assert missing_task.status_code == 404
    assert missing_task.json()["error"]["code"] == "task_not_found"


@pytest.mark.asyncio
async def test_analyst_workflow_rejects_invalid_inputs_and_duplicate_actions() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    analyst_user = app.state.access_services.repository.get_user_by_username("analyst@example.test")
    admin_user = app.state.access_services.repository.get_user_by_username("admin@example.test")
    assert analyst_user is not None
    assert admin_user is not None
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        ticket_id = await _approved_ticket(client)
        manager = await login(client, "rfa.manager@example.test")
        invalid_analyst = await client.post(
            f"/api/v1/analyst/tasks/{ticket_id}/assign",
            headers={"X-CSRF-Token": str(manager["csrfToken"])},
            json={"analystUserIds": [str(admin_user.user_id)], "teamId": str(_rfa_team(app))},
        )
        assigned = await client.post(
            f"/api/v1/analyst/tasks/{ticket_id}/assign",
            headers={"X-CSRF-Token": str(manager["csrfToken"])},
            json={"analystUserIds": [str(analyst_user.user_id)], "teamId": str(_rfa_team(app))},
        )
        product = await _published_for_analyst(client, app)
        analyst = await login(client, "analyst@example.test")
        team_id = next(
            team.team_id
            for team in app.state.team_repository.list_teams()
            if team.kind.value == "rfa"
        )
        candidates = await client.get(f"/api/v1/analyst/candidates?route=rfa&teamId={team_id}")
        linked = await client.post(
            f"/api/v1/analyst/tasks/{ticket_id}/products",
            headers={"X-CSRF-Token": str(analyst["csrfToken"])},
            json={"productId": product["id"]},
        )
        duplicate_link = await client.post(
            f"/api/v1/analyst/tasks/{ticket_id}/products",
            headers={"X-CSRF-Token": str(analyst["csrfToken"])},
            json={"productId": product["id"]},
        )
        missing_package = await client.patch(
            f"/api/v1/analyst/tasks/{ticket_id}/work-packages/{uuid4()}",
            headers={"X-CSRF-Token": str(analyst["csrfToken"])},
            json={"status": "complete"},
        )
        draft_required = await client.post(
            f"/api/v1/analyst/tasks/{ticket_id}/submit",
            headers={"X-CSRF-Token": str(analyst["csrfToken"])},
        )
        bad_payload = _draft_payload("Invalid draft")
        bad_payload["assets"][0]["sha256"] = "x" * 64
        bad_draft = await client.post(
            f"/api/v1/analyst/tasks/{ticket_id}/drafts",
            headers={"X-CSRF-Token": str(analyst["csrfToken"])},
            json=bad_payload,
        )
        valid_draft = await client.post(
            f"/api/v1/analyst/tasks/{ticket_id}/drafts",
            headers={"X-CSRF-Token": str(analyst["csrfToken"])},
            json=_draft_payload("Valid draft"),
        )
        task = assigned.json()
        for package in task["workPackages"]:
            await client.patch(
                f"/api/v1/analyst/tasks/{ticket_id}/work-packages/{package['id']}",
                headers={"X-CSRF-Token": str(analyst["csrfToken"])},
                json={"status": "complete"},
            )
        submitted = await client.post(
            f"/api/v1/analyst/tasks/{ticket_id}/submit",
            headers={"X-CSRF-Token": str(analyst["csrfToken"])},
        )
        note_after_qc = await client.post(
            f"/api/v1/analyst/tasks/{ticket_id}/notes",
            headers={"X-CSRF-Token": str(analyst["csrfToken"])},
            json={"body": "Too late for a note."},
        )

    assert invalid_analyst.status_code == 422
    assert invalid_analyst.json()["error"]["code"] == "invalid_analyst"
    assert candidates.status_code == 403
    assert linked.status_code == 200
    assert duplicate_link.status_code == 409
    assert duplicate_link.json()["error"]["code"] == "product_already_linked"
    assert missing_package.status_code == 404
    assert draft_required.status_code == 409
    assert draft_required.json()["error"]["code"] == "draft_required"
    assert bad_draft.status_code == 409
    assert bad_draft.json()["error"]["code"] == "asset_hash_invalid"
    assert valid_draft.status_code == 200
    assert submitted.status_code == 200
    assert note_after_qc.status_code == 409
    assert note_after_qc.json()["error"]["code"] == "invalid_ticket_state"


async def _assigned_ticket(client: AsyncClient, app: FastAPI) -> str:
    ticket_id = await _approved_ticket(client)
    analyst_user = app.state.access_services.repository.get_user_by_username("analyst@example.test")
    assert analyst_user is not None
    manager = await login(client, "rfa.manager@example.test")
    assigned = await client.post(
        f"/api/v1/analyst/tasks/{ticket_id}/assign",
        headers={"X-CSRF-Token": str(manager["csrfToken"])},
        json={"analystUserIds": [str(analyst_user.user_id)], "teamId": str(_rfa_team(app))},
    )
    assert assigned.status_code == 200
    return ticket_id


async def _approved_ticket(client: AsyncClient) -> str:
    return await analyst_assignment_ticket(client)


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
