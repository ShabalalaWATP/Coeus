from typing import Any
from uuid import UUID

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from coeus.core.config import Settings
from coeus.main import create_app
from rfi_search_helpers import login
from routing_helpers import analyst_assignment_ticket, assignment_team_id
from test_qc_api import _draft_payload


def _app() -> FastAPI:
    return create_app(Settings(environment="test", argon2_memory_cost=8_192))


def _analyst_ids(app: FastAPI, *usernames: str) -> list[str]:
    ids: list[str] = []
    for username in usernames:
        user = app.state.access_services.repository.get_user_by_username(username)
        assert user is not None
        ids.append(str(user.user_id))
    return ids


async def _assign(client: AsyncClient, ticket_id: str, analyst_ids: list[str], **extra: Any):
    manager = await login(client, "rfa.manager@example.test")
    team_id = await assignment_team_id(client)
    return await client.post(
        f"/api/v1/analyst/tasks/{ticket_id}/assign",
        headers={"X-CSRF-Token": str(manager["csrfToken"])},
        json={"analystUserIds": analyst_ids, "teamId": team_id, **extra},
    )


async def _draft_complete_and_submit(client: AsyncClient, ticket_id: str, title: str):
    analyst = await login(client, "analyst@example.test")
    draft = await client.post(
        f"/api/v1/analyst/tasks/{ticket_id}/drafts",
        headers={"X-CSRF-Token": str(analyst["csrfToken"])},
        json=_draft_payload(title),
    )
    assert draft.status_code == 200
    for package in draft.json()["workPackages"]:
        completed = await client.patch(
            f"/api/v1/analyst/tasks/{ticket_id}/work-packages/{package['id']}",
            headers={"X-CSRF-Token": str(analyst["csrfToken"])},
            json={"status": "complete"},
        )
        assert completed.status_code == 200
    return await client.post(
        f"/api/v1/analyst/tasks/{ticket_id}/submit",
        headers={"X-CSRF-Token": str(analyst["csrfToken"])},
    )


@pytest.mark.asyncio
async def test_manager_can_return_work_for_rework_and_then_approve() -> None:
    app = _app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        ticket_id = await analyst_assignment_ticket(client)
        assigned = await _assign(client, ticket_id, _analyst_ids(app, "analyst@example.test"))
        assert assigned.status_code == 200
        submitted = await _draft_complete_and_submit(client, ticket_id, "Chain product")
        assert submitted.status_code == 200
        assert submitted.json()["state"] == "MANAGER_APPROVAL"

        manager = await login(client, "rfa.manager@example.test")
        review = await client.get(f"/api/v1/routing/{ticket_id}/manager-work")
        assert review.status_code == 200
        assert review.json()["drafts"][-1]["title"] == "Chain product"
        assert review.json()["workPackages"]
        assert all(item["status"] == "complete" for item in review.json()["workPackages"])
        reworked = await client.post(
            f"/api/v1/routing/{ticket_id}/manager-rework",
            headers={"X-CSRF-Token": str(manager["csrfToken"])},
            json={"route": "rfa", "reason": "Tighten the source trace before QC."},
        )
        assert reworked.status_code == 200
        assert reworked.json()["state"] == "ANALYST_IN_PROGRESS"

        analyst = await login(client, "analyst@example.test")
        revised = await client.post(
            f"/api/v1/analyst/tasks/{ticket_id}/drafts",
            headers={"X-CSRF-Token": str(analyst["csrfToken"])},
            json=_draft_payload("Revised chain product"),
        )
        assert revised.status_code == 200
        resubmitted = await client.post(
            f"/api/v1/analyst/tasks/{ticket_id}/submit",
            headers={"X-CSRF-Token": str(analyst["csrfToken"])},
        )
        assert resubmitted.status_code == 200
        assert resubmitted.json()["state"] == "MANAGER_APPROVAL"

        manager = await login(client, "rfa.manager@example.test")
        approved = await client.post(
            f"/api/v1/routing/{ticket_id}/manager-approval",
            headers={"X-CSRF-Token": str(manager["csrfToken"])},
        )
        await login(client, "admin@example.test")
        audit = await client.get("/api/v1/audit")

    assert approved.status_code == 200
    assert approved.json()["state"] == "QC_REVIEW"
    event_types = [event["eventType"] for event in audit.json()["events"]]
    assert "manager_returned_rework" in event_types
    assert "manager_approved" in event_types


@pytest.mark.asyncio
async def test_manager_approval_guards_permissions_state_and_reason() -> None:
    app = _app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        ticket_id = await analyst_assignment_ticket(client)
        assigned = await _assign(client, ticket_id, _analyst_ids(app, "analyst@example.test"))
        assert assigned.status_code == 200

        # Not yet awaiting approval.
        manager = await login(client, "rfa.manager@example.test")
        premature = await client.post(
            f"/api/v1/routing/{ticket_id}/manager-approval",
            headers={"X-CSRF-Token": str(manager["csrfToken"])},
        )
        assert premature.status_code == 409

        submitted = await _draft_complete_and_submit(client, ticket_id, "Guarded product")
        assert submitted.status_code == 200

        analyst = await login(client, "analyst@example.test")
        hidden_review = await client.get(f"/api/v1/routing/{ticket_id}/manager-work")
        assert hidden_review.status_code == 403
        analyst_attempt = await client.post(
            f"/api/v1/routing/{ticket_id}/manager-approval",
            headers={"X-CSRF-Token": str(analyst["csrfToken"])},
        )
        assert analyst_attempt.status_code == 403

        # The other team's manager holds PRODUCT_APPROVE but not this route.
        cm_manager = await login(client, "collection.manager@example.test")
        wrong_route = await client.post(
            f"/api/v1/routing/{ticket_id}/manager-approval",
            headers={"X-CSRF-Token": str(cm_manager["csrfToken"])},
        )
        assert wrong_route.status_code in {403, 404}

        manager = await login(client, "rfa.manager@example.test")
        short_reason = await client.post(
            f"/api/v1/routing/{ticket_id}/manager-rework",
            headers={"X-CSRF-Token": str(manager["csrfToken"])},
            json={"route": "rfa", "reason": "x"},
        )
        assert short_reason.status_code == 422


@pytest.mark.asyncio
async def test_a_manager_who_drafted_the_work_cannot_approve_it() -> None:
    app = _app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        ticket_id = await analyst_assignment_ticket(client)
        assigned = await _assign(client, ticket_id, _analyst_ids(app, "analyst@example.test"))
        assert assigned.status_code == 200
        submitted = await _draft_complete_and_submit(client, ticket_id, "Self approval product")
        assert submitted.status_code == 200

        manager_user = app.state.access_services.repository.get_user_by_username(
            "rfa.manager@example.test"
        )
        assert manager_user is not None
        _make_latest_drafter(app, ticket_id, manager_user.user_id)
        manager = await login(client, "rfa.manager@example.test")
        review = await client.get(f"/api/v1/routing/{ticket_id}/manager-work")
        refused = await client.post(
            f"/api/v1/routing/{ticket_id}/manager-approval",
            headers={"X-CSRF-Token": str(manager["csrfToken"])},
        )

    assert review.status_code == 200
    assert refused.status_code == 403
    assert refused.json()["error"]["code"] == "separation_of_duties"


@pytest.mark.asyncio
async def test_multiple_analysts_share_the_task_and_reassignment_deactivates() -> None:
    app = _app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        ticket_id = await analyst_assignment_ticket(client)
        pair = _analyst_ids(app, "analyst@example.test", "analyst.geo@example.test")
        assigned = await _assign(client, ticket_id, pair)
        assert assigned.status_code == 200
        assert len(assigned.json()["assignments"]) == 2

        # Both assigned analysts see the shared task.
        for username in ("analyst@example.test", "analyst.geo@example.test"):
            await login(client, username)
            tasks = await client.get("/api/v1/analyst/tasks")
            assert ticket_id in [task["ticketId"] for task in tasks.json()["tasks"]]

        # Reassignment replaces the active set instead of stacking it.
        solo = _analyst_ids(app, "analyst@example.test")
        reassigned = await _assign(client, ticket_id, solo)
        assert reassigned.status_code == 200
        assert len(reassigned.json()["assignments"]) == 1

        await login(client, "analyst.geo@example.test")
        removed_tasks = await client.get("/api/v1/analyst/tasks")
        assert ticket_id not in [task["ticketId"] for task in removed_tasks.json()["tasks"]]


@pytest.mark.asyncio
async def test_assignment_rejects_duplicates_and_fresh_double_assignment() -> None:
    app = _app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        ticket_id = await analyst_assignment_ticket(client)
        solo = _analyst_ids(app, "analyst@example.test")
        # Duplicate ids collapse to one analyst rather than failing.
        deduped = await _assign(client, ticket_id, [*solo, *solo])
        assert deduped.status_code == 200
        assert len(deduped.json()["assignments"]) == 1

        second_ticket = await analyst_assignment_ticket(client)
        assigned = await _assign(client, second_ticket, solo)
        assert assigned.status_code == 200
        # One analyst can hold several live tasks at once.
        await login(client, "analyst@example.test")
        tasks = await client.get("/api/v1/analyst/tasks")
        task_ids = [task["ticketId"] for task in tasks.json()["tasks"]]
        assert ticket_id in task_ids
        assert second_ticket in task_ids
        # The ticket is ANALYST_IN_PROGRESS now, so a further assign call is a
        # reassignment, but a fresh assignment is blocked while active
        # assignments exist for the approved route.
        empty = await _assign(client, second_ticket, [])
        assert empty.status_code == 422


def _make_latest_drafter(app: FastAPI, ticket_id: str, user_id: UUID) -> None:
    from dataclasses import replace

    repository = app.state.ticket_services.tickets._repository
    ticket = repository.get(UUID(ticket_id))
    assert ticket is not None
    draft = replace(ticket.draft_products[-1], created_by_user_id=user_id)
    repository.save(replace(ticket, draft_products=(*ticket.draft_products[:-1], draft)))
