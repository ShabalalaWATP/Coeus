import pytest
from httpx import ASGITransport, AsyncClient

from coeus.core.config import Settings
from coeus.main import create_app
from rfi_search_helpers import login
from routing_helpers import assignment_team_id
from test_analyst_api import _approved_ticket, _assigned_ticket, _draft_payload


@pytest.mark.asyncio
async def test_manager_can_reassign_in_progress_ticket_to_another_analyst() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    repository = app.state.access_services.repository
    replacement = repository.get_user_by_username("analyst.2@example.test")
    assert replacement is not None

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        ticket_id = await _assigned_ticket(client, app)
        analyst = await login(client, "analyst@example.test")
        before = await client.get(f"/api/v1/analyst/tasks/{ticket_id}")
        assert analyst["user"]["username"] == "analyst@example.test"
        manager = await login(client, "rfa.manager@example.test")
        team_id = await assignment_team_id(client)
        reassigned = await client.post(
            f"/api/v1/analyst/tasks/{ticket_id}/assign",
            headers={"X-CSRF-Token": str(manager["csrfToken"])},
            json={"analystUserIds": [str(replacement.user_id)], "teamId": team_id},
        )
        new_analyst = await login(client, "analyst.2@example.test")
        tasks = await client.get("/api/v1/analyst/tasks")
        admin = await login(client, "admin@example.test")
        audit = await client.get("/api/v1/audit")

    assert reassigned.status_code == 200
    assert reassigned.json()["state"] == "ANALYST_IN_PROGRESS"
    assert [item["analystUserId"] for item in reassigned.json()["assignments"]] == [
        str(replacement.user_id)
    ]
    # Existing work packages carry over; reassignment does not add more.
    assert reassigned.json()["workPackages"] == before.json()["workPackages"]
    assert new_analyst["user"]["username"] == "analyst.2@example.test"
    assert [task["ticketId"] for task in tasks.json()["tasks"]] == [ticket_id]
    assert admin["user"]["username"] == "admin@example.test"
    assert "analyst_reassigned" in [event["eventType"] for event in audit.json()["events"]]


@pytest.mark.asyncio
async def test_reassignment_is_blocked_before_first_assignment_completes() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    analyst_user = app.state.access_services.repository.get_user_by_username("analyst@example.test")
    assert analyst_user is not None

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        ticket_id = await _approved_ticket(client)
        manager = await login(client, "rfa.manager@example.test")
        team_id = await assignment_team_id(client)
        assigned = await client.post(
            f"/api/v1/analyst/tasks/{ticket_id}/assign",
            headers={"X-CSRF-Token": str(manager["csrfToken"])},
            json={"analystUserIds": [str(analyst_user.user_id)], "teamId": team_id},
        )
        analyst = await login(client, "analyst@example.test")
        draft = await client.post(
            f"/api/v1/analyst/tasks/{ticket_id}/drafts",
            headers={"X-CSRF-Token": str(analyst["csrfToken"])},
            json=_draft_payload("Arctic draft"),
        )
        for package in draft.json()["workPackages"]:
            await client.patch(
                f"/api/v1/analyst/tasks/{ticket_id}/work-packages/{package['id']}",
                headers={"X-CSRF-Token": str(analyst["csrfToken"])},
                json={"status": "complete"},
            )
        submitted = await client.post(
            f"/api/v1/analyst/tasks/{ticket_id}/submit",
            headers={"X-CSRF-Token": str(analyst["csrfToken"])},
        )
        manager = await login(client, "rfa.manager@example.test")
        after_qc = await client.post(
            f"/api/v1/analyst/tasks/{ticket_id}/assign",
            headers={"X-CSRF-Token": str(manager["csrfToken"])},
            json={"analystUserIds": [str(analyst_user.user_id)], "teamId": team_id},
        )

    assert assigned.status_code == 200
    assert submitted.status_code == 200
    # Once the ticket leaves the analyst states, assignment is closed again.
    assert after_qc.status_code == 409
    assert after_qc.json()["error"]["code"] == "invalid_ticket_state"


@pytest.mark.asyncio
async def test_rework_ticket_can_be_reassigned_after_analyst_deactivation() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    repository = app.state.access_services.repository
    original = repository.get_user_by_username("analyst@example.test")
    replacement = repository.get_user_by_username("analyst.2@example.test")
    assert original is not None and replacement is not None

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        ticket_id = await _assigned_ticket(client, app)
        analyst = await login(client, "analyst@example.test")
        draft = await client.post(
            f"/api/v1/analyst/tasks/{ticket_id}/drafts",
            headers={"X-CSRF-Token": str(analyst["csrfToken"])},
            json=_draft_payload("Arctic rework draft"),
        )
        for package in draft.json()["workPackages"]:
            await client.patch(
                f"/api/v1/analyst/tasks/{ticket_id}/work-packages/{package['id']}",
                headers={"X-CSRF-Token": str(analyst["csrfToken"])},
                json={"status": "complete"},
            )
        await client.post(
            f"/api/v1/analyst/tasks/{ticket_id}/submit",
            headers={"X-CSRF-Token": str(analyst["csrfToken"])},
        )
        manager = await login(client, "rfa.manager@example.test")
        await client.post(
            f"/api/v1/routing/{ticket_id}/manager-approval",
            headers={"X-CSRF-Token": str(manager["csrfToken"])},
        )
        qc = await login(client, "qc.manager@example.test")
        rejected = await client.post(
            f"/api/v1/qc/products/{ticket_id}/reject",
            headers={"X-CSRF-Token": str(qc["csrfToken"])},
            json={"reason": "Restate the mock sourcing chain."},
        )
        admin = await login(client, "admin@example.test")
        disabled = await client.put(
            f"/api/v1/admin/users/{original.user_id}/status",
            headers={"X-CSRF-Token": str(admin["csrfToken"])},
            json={"isActive": False},
        )
        manager = await login(client, "rfa.manager@example.test")
        reassigned = await client.post(
            f"/api/v1/analyst/tasks/{ticket_id}/assign",
            headers={"X-CSRF-Token": str(manager["csrfToken"])},
            json={
                "analystUserIds": [str(replacement.user_id)],
                "teamId": await assignment_team_id(client),
            },
        )
        new_analyst = await login(client, "analyst.2@example.test")
        revised = await client.post(
            f"/api/v1/analyst/tasks/{ticket_id}/drafts",
            headers={"X-CSRF-Token": str(new_analyst["csrfToken"])},
            json=_draft_payload("Arctic rework draft revised"),
        )
        resubmitted = await client.post(
            f"/api/v1/analyst/tasks/{ticket_id}/submit",
            headers={"X-CSRF-Token": str(new_analyst["csrfToken"])},
        )

    assert rejected.json()["state"] == "REWORK_REQUIRED"
    assert disabled.status_code == 200
    assert reassigned.status_code == 200
    assert reassigned.json()["state"] == "REWORK_REQUIRED"
    assert [item["analystUserId"] for item in reassigned.json()["assignments"]] == [
        str(replacement.user_id)
    ]
    assert revised.status_code == 200
    assert resubmitted.status_code == 200
    assert resubmitted.json()["state"] == "QC_REVIEW"


@pytest.mark.asyncio
async def test_setting_work_package_to_current_status_is_a_no_op() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        ticket_id = await _assigned_ticket(client, app)
        analyst = await login(client, "analyst@example.test")
        task = await client.get(f"/api/v1/analyst/tasks/{ticket_id}")
        package = task.json()["workPackages"][0]
        first = await client.patch(
            f"/api/v1/analyst/tasks/{ticket_id}/work-packages/{package['id']}",
            headers={"X-CSRF-Token": str(analyst["csrfToken"])},
            json={"status": "complete"},
        )
        repeat = await client.patch(
            f"/api/v1/analyst/tasks/{ticket_id}/work-packages/{package['id']}",
            headers={"X-CSRF-Token": str(analyst["csrfToken"])},
            json={"status": "complete"},
        )

    assert first.status_code == 200
    assert repeat.status_code == 200
    statuses = {item["id"]: item["status"] for item in repeat.json()["workPackages"]}
    assert statuses[package["id"]] == "complete"
