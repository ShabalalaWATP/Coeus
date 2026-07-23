from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient

from coeus.core.config import Settings
from coeus.core.permissions import Permission
from coeus.domain.auth import RoleName
from coeus.domain.enums import TicketState
from coeus.domain.rbac import ROLE_DEFINITIONS
from coeus.main import create_app
from coeus.services.ticket_records import timeline
from rfi_search_helpers import login, submitted_ticket


def _app():
    return create_app(
        Settings(
            environment="test",
            argon2_memory_cost=8_192,
            automatic_request_discovery_enabled=False,
        )
    )


@pytest.mark.asyncio
async def test_rfi_results_hide_product_derived_signals_from_unauthorised_viewers() -> None:
    app = _app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        owner = await login(client, "user@example.test")
        csrf = str(owner["csrfToken"])
        ticket_id = await submitted_ticket(client, csrf)
        for username in ("colleague@example.test", "collection.team@example.test"):
            tagged = await client.post(
                f"/api/v1/tickets/{ticket_id}/collaborators",
                headers={"X-CSRF-Token": csrf},
                json={"username": username, "access": "viewer"},
            )
            assert tagged.status_code == 200

        owner_result = await client.post(
            f"/api/v1/rfi-search/{ticket_id}/run",
            headers={"X-CSRF-Token": csrf},
        )
        assert owner_result.status_code == 200
        assert owner_result.json()["ticketState"] == "RFI_MATCH_OFFERED"
        assert owner_result.json()["outcome"] == "offers"
        assert owner_result.json()["offers"]
        owner_ticket = await client.get(f"/api/v1/tickets/{ticket_id}")
        assert owner_ticket.json()["state"] == "RFI_MATCH_OFFERED"

        await login(client, "colleague@example.test")
        authorised = await client.get(f"/api/v1/rfi-search/{ticket_id}/results")
        authorised_ticket = await client.get(f"/api/v1/tickets/{ticket_id}")
        authorised_list = await client.get("/api/v1/tickets")
        assert authorised.status_code == 200
        assert authorised.json()["ticketState"] == "RFI_MATCH_OFFERED"
        assert authorised.json()["outcome"] == "offers"
        assert authorised.json()["offers"]
        assert authorised_ticket.json()["state"] == "RFI_MATCH_OFFERED"
        assert _ticket_from_list(authorised_list, ticket_id)["state"] == "RFI_MATCH_OFFERED"

        await login(client, "collection.team@example.test")
        hidden_positive = await client.get(f"/api/v1/rfi-search/{ticket_id}/results")
        hidden_ticket = await client.get(f"/api/v1/tickets/{ticket_id}")
        hidden_list = await client.get("/api/v1/tickets")
        assert hidden_positive.status_code == 200

        stored = app.state.ticket_services.tickets._repository.get(UUID(ticket_id))
        assert stored is not None and stored.search_metrics
        no_match_metric = replace(
            stored.search_metrics[-1],
            candidate_count=0,
            offered_count=0,
            rejected_count=0,
            accepted_product_id=None,
            outcome="no_match",
        )
        app.state.ticket_services.tickets.save_system_update(
            replace(
                stored,
                state=TicketState.NEW_TASKING_CONSENT,
                product_offers=(),
                search_evidence=(),
                search_metrics=(*stored.search_metrics[:-1], no_match_metric),
                visible_product_matches=(),
                timeline=(
                    *stored.timeline,
                    timeline(
                        stored.ticket_id,
                        stored.requester_user_id,
                        "rfi_no_match",
                        "No existing product matched this request.",
                    ),
                ),
            )
        )
        no_visible_result = await client.get(f"/api/v1/rfi-search/{ticket_id}/results")
        no_visible_ticket = await client.get(f"/api/v1/tickets/{ticket_id}")
        no_visible_list = await client.get("/api/v1/tickets")

    def protected_projection(response) -> dict[str, object]:
        body = response.json()
        return {
            "ticketState": body["ticketState"],
            "outcome": body["outcome"],
            "metricOutcome": body["metrics"]["outcome"],
            "candidateCount": body["metrics"]["candidateCount"],
            "offeredCount": body["metrics"]["offeredCount"],
            "rejectedCount": body["metrics"]["rejectedCount"],
            "acceptedProductId": body["metrics"]["acceptedProductId"],
            "offers": body["offers"],
        }

    expected_neutral = {
        "ticketState": "RFI_SEARCH_INCOMPLETE",
        "outcome": "incomplete",
        "metricOutcome": "incomplete",
        "candidateCount": 0,
        "offeredCount": 0,
        "rejectedCount": 0,
        "acceptedProductId": None,
        "offers": [],
    }
    assert protected_projection(hidden_positive) == expected_neutral
    assert protected_projection(no_visible_result) == expected_neutral
    assert _ticket_signal_projection(hidden_ticket) == _ticket_signal_projection(no_visible_ticket)
    assert _ticket_signal_projection(hidden_ticket)["state"] == "RFI_SEARCH_INCOMPLETE"
    assert "rfi_no_match" not in _ticket_signal_projection(no_visible_ticket)["timeline"]
    assert _ticket_summary_signal(_ticket_from_list(hidden_list, ticket_id)) == (
        _ticket_summary_signal(_ticket_from_list(no_visible_list, ticket_id))
    )


@pytest.mark.asyncio
async def test_non_rfi_collaborator_ticket_projection_is_unchanged() -> None:
    app = _app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        owner = await login(client, "user@example.test")
        created = await client.post(
            "/api/v1/chat/messages",
            headers={"X-CSRF-Token": str(owner["csrfToken"])},
            json={"message": "Need help defining a synthetic training requirement."},
        )
        ticket_id = created.json()["id"]
        tagged = await client.post(
            f"/api/v1/tickets/{ticket_id}/collaborators",
            headers={"X-CSRF-Token": str(owner["csrfToken"])},
            json={"username": "collection.team@example.test", "access": "viewer"},
        )
        await login(client, "collection.team@example.test")
        collaborator = await client.get(f"/api/v1/tickets/{ticket_id}")
        listed = await client.get("/api/v1/tickets")

    assert created.status_code == 201
    assert tagged.status_code == 200
    assert collaborator.status_code == 200
    assert collaborator.json()["state"] == created.json()["state"]
    assert collaborator.json()["customerStatus"]["code"] == created.json()["customerStatus"]["code"]
    assert _ticket_from_list(listed, ticket_id)["state"] == created.json()["state"]


def _ticket_from_list(response, ticket_id: str) -> dict[str, object]:
    return next(ticket for ticket in response.json()["tickets"] if ticket["id"] == ticket_id)


def _ticket_summary_signal(ticket: dict[str, object]) -> dict[str, object]:
    status = ticket["customerStatus"]
    assert isinstance(status, dict)
    return {"state": ticket["state"], "customerStatus": status["code"]}


def _ticket_signal_projection(response) -> dict[str, object]:
    body = response.json()
    status = body["customerStatus"]
    return {
        "state": body["state"],
        "statusCode": status["code"],
        "statusLabel": status["label"],
        "statusExplanation": status["explanation"],
        "currentLeg": status["currentLeg"],
        "actionRequired": status["actionRequired"],
        "actionType": status["actionType"],
        "nextMilestone": status["nextMilestone"],
        "journey": [(item["code"], item["status"]) for item in status["journey"]],
        "visibleProductMatches": body["visibleProductMatches"],
        "releasedProductIds": body["releasedProductIds"],
        "timeline": [item["eventType"] for item in body["timeline"]],
    }


@pytest.mark.asyncio
async def test_calendar_reauthorises_manager_permission_at_each_write() -> None:
    app = _app()
    repository = app.state.access_services.repository
    manager_user = repository.get_user_by_username("rfa.manager@example.test")
    target_user = repository.get_user_by_username("analyst.4@example.test")
    assert manager_user is not None and target_user is not None
    entry_date = (datetime.now(UTC).date() + timedelta(days=3)).isoformat()

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        manager = await login(client, manager_user.username)
        teams = await client.get("/api/v1/teams")
        team_id = next(
            team["id"] for team in teams.json()["teams"] if team["name"] == "RFA Assessment Team"
        )
        legitimate = await client.post(
            f"/api/v1/teams/{team_id}/calendar",
            headers={"X-CSRF-Token": str(manager["csrfToken"])},
            json={
                "userId": str(target_user.user_id),
                "date": entry_date,
                "status": "leave",
                "note": "Current manager control.",
            },
        )
        assert legitimate.status_code == 200

        admin = await login(client, "admin@example.test")
        demoted = await client.put(
            f"/api/v1/admin/users/{manager_user.user_id}/roles",
            headers={"X-CSRF-Token": str(admin["csrfToken"])},
            json={"roles": ["Customer"]},
        )
        assert demoted.status_code == 200

        former_manager = await login(client, manager_user.username)
        cross_user = await client.post(
            f"/api/v1/teams/{team_id}/calendar",
            headers={"X-CSRF-Token": str(former_manager["csrfToken"])},
            json={
                "userId": str(target_user.user_id),
                "date": entry_date,
                "status": "on_task",
            },
        )
        cross_user_delete = await client.delete(
            f"/api/v1/teams/{team_id}/calendar/{legitimate.json()['id']}",
            headers={"X-CSRF-Token": str(former_manager["csrfToken"])},
        )
        own = await client.post(
            f"/api/v1/teams/{team_id}/calendar",
            headers={"X-CSRF-Token": str(former_manager["csrfToken"])},
            json={
                "userId": str(manager_user.user_id),
                "date": entry_date,
                "status": "leave",
                "note": "Member self-service remains available.",
            },
        )

    refreshed = repository.get_user(manager_user.user_id)
    team = app.state.team_repository.get_team(UUID(team_id))
    assert refreshed is not None and team is not None
    assert Permission.TEAM_MANAGE not in refreshed.permissions
    assert refreshed.user_id in team.manager_user_ids
    assert cross_user.status_code == 403
    assert cross_user_delete.status_code == 403
    assert own.status_code == 200


@pytest.mark.asyncio
async def test_global_audit_remains_admin_only_without_breaking_jioc_oversight() -> None:
    app = _app()
    marker_id = "00000000-0000-4000-8000-00000000d021"
    app.state.auth_service.audit_log.record(
        "product_break_glass_accessed",
        "synthetic-protected-actor",
        {"product_id": marker_id, "reason": "Synthetic restricted context"},
    )

    assert Permission.AUDIT_READ not in ROLE_DEFINITIONS[RoleName.JIOC_MANAGER].permissions
    assert Permission.JIOC_OVERSIGHT in ROLE_DEFINITIONS[RoleName.JIOC_MANAGER].permissions
    assert Permission.AUDIT_READ in ROLE_DEFINITIONS[RoleName.ADMINISTRATOR].permissions

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        await login(client, "jioc.team@example.test")
        denied = await client.get("/api/v1/audit")
        oversight = await client.get("/api/v1/routing/oversight")
        await login(client, "admin@example.test")
        admin_audit = await client.get("/api/v1/audit")

    assert denied.status_code == 403
    assert oversight.status_code == 200
    assert admin_audit.status_code == 200
    marker = next(
        event
        for event in admin_audit.json()["events"]
        if event["metadata"].get("product_id") == marker_id
    )
    assert marker["actorUserId"] == "synthetic-protected-actor"
    assert marker["metadata"]["reason"] == "Synthetic restricted context"
