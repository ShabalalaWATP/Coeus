from dataclasses import replace
from datetime import date
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from coeus.core.config import Settings
from coeus.domain.teams import OrgTeam, TeamKind
from coeus.main import create_app
from coeus.services.routing_oversight import RoutingOversightService
from coeus.services.user_admin import UserAdminService
from rfi_search_helpers import login
from routing_helpers import analyst_assignment_ticket, assignment_team_id, route_assessment_ticket
from test_qc_api import _draft_payload


@pytest.mark.asyncio
async def test_structured_routing_clarification_resumes_jioc() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        ticket_id = await analyst_assignment_ticket(client)
        ticket = app.state.ticket_services.tickets._repository.get(UUID(ticket_id))
        assert ticket is not None
        app.state.ticket_services.tickets._repository.save(
            replace(ticket, state=ticket.state.INFO_REQUIRED)
        )
        customer = await login(client, "user@example.test")
        response = await client.patch(
            f"/api/v1/tickets/{ticket_id}/intake",
            headers={"X-CSRF-Token": str(customer["csrfToken"])},
            json={"description": "Clarified structured requirement."},
        )
    assert response.status_code == 200
    assert response.json()["state"] == "JIOC_REVIEW"


@pytest.mark.asyncio
async def test_rework_requires_a_newer_draft() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        ticket_id = await analyst_assignment_ticket(client)
        analyst = app.state.access_services.repository.get_user_by_username("analyst@example.test")
        assert analyst is not None
        manager = await login(client, "rfa.manager@example.test")
        team_id = await assignment_team_id(client)
        assigned = await client.post(
            f"/api/v1/analyst/tasks/{ticket_id}/assign",
            headers={"X-CSRF-Token": str(manager["csrfToken"])},
            json={"analystUserIds": [str(analyst.user_id)], "teamId": team_id},
        )
        worker = await login(client, "analyst@example.test")
        drafted = await client.post(
            f"/api/v1/analyst/tasks/{ticket_id}/drafts",
            headers={"X-CSRF-Token": str(worker["csrfToken"])},
            json=_draft_payload("Initial integrity draft"),
        )
        for package in drafted.json()["workPackages"]:
            await client.patch(
                f"/api/v1/analyst/tasks/{ticket_id}/work-packages/{package['id']}",
                headers={"X-CSRF-Token": str(worker["csrfToken"])},
                json={"status": "complete"},
            )
        await client.post(
            f"/api/v1/analyst/tasks/{ticket_id}/submit",
            headers={"X-CSRF-Token": str(worker["csrfToken"])},
        )
        manager = await login(client, "rfa.manager@example.test")
        await client.post(
            f"/api/v1/routing/{ticket_id}/manager-rework",
            headers={"X-CSRF-Token": str(manager["csrfToken"])},
            json={"route": "rfa", "reason": "Revise this product."},
        )
        worker = await login(client, "analyst@example.test")
        unchanged = await client.post(
            f"/api/v1/analyst/tasks/{ticket_id}/submit",
            headers={"X-CSRF-Token": str(worker["csrfToken"])},
        )
    assert assigned.status_code == 200
    assert unchanged.status_code == 409
    assert unchanged.json()["error"]["code"] == "revised_draft_required"


@pytest.mark.asyncio
async def test_analyst_detail_uses_the_list_state_boundary() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        ticket_id = await analyst_assignment_ticket(client)
        analyst = app.state.access_services.repository.get_user_by_username("analyst@example.test")
        assert analyst is not None
        manager = await login(client, "rfa.manager@example.test")
        team_id = await assignment_team_id(client)
        await client.post(
            f"/api/v1/analyst/tasks/{ticket_id}/assign",
            headers={"X-CSRF-Token": str(manager["csrfToken"])},
            json={"analystUserIds": [str(analyst.user_id)], "teamId": team_id},
        )
        ticket = app.state.ticket_services.tickets._repository.get(UUID(ticket_id))
        assert ticket is not None
        app.state.ticket_services.tickets._repository.save(
            replace(ticket, state=ticket.state.CANCELLED)
        )
        await login(client, "analyst@example.test")
        response = await client.get(f"/api/v1/analyst/tasks/{ticket_id}")
        await login(client, "jioc.team@example.test")
        oversight = await client.get("/api/v1/routing/oversight")
    assert response.status_code == 404
    assert sum(item["liveTaskCount"] for item in oversight.json()["teams"]) == 0
    assert sum(item["liveTaskCount"] for item in oversight.json()["analysts"]) == 0


@pytest.mark.asyncio
async def test_jioc_oversight_is_bounded_and_content_safe() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        await analyst_assignment_ticket(client)
        await login(client, "jioc.team@example.test")
        response = await client.get("/api/v1/routing/oversight")
        body = response.json()
        await login(client, "user@example.test")
        forbidden = await client.get("/api/v1/routing/oversight")
    assert response.status_code == 200
    assert len(body["tasks"]) <= 200
    assert not ({"notes", "drafts", "intake", "products"} & set(body["tasks"][0]))
    assert forbidden.status_code == 403


def test_credential_reset_restores_attempt_state_when_change_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    service: UserAdminService = app.state.user_admin_service
    admin = app.state.access_services.repository.get_user_by_username("admin@example.test")
    target = app.state.access_services.repository.get_user_by_username("user@example.test")
    assert admin is not None and target is not None
    service._login_attempts.record_failure(target.username, 3, 60)
    before = service._login_attempts.snapshot()
    monkeypatch.setattr(
        service, "_apply_and_audit", lambda *_args: (_ for _ in ()).throw(RuntimeError())
    )
    with pytest.raises(RuntimeError):
        service.reset_credential(admin, target.user_id)
    assert service._login_attempts.snapshot() == before


@pytest.mark.asyncio
async def test_area_manager_selects_an_authoritative_same_kind_team() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    analyst = app.state.access_services.repository.get_user_by_username("analyst.geo@example.test")
    assert analyst is not None
    team = OrgTeam(
        team_id=uuid4(),
        name="RFA Geospatial Team",
        kind=TeamKind.RFA,
        member_user_ids=(analyst.user_id,),
    )
    app.state.team_repository.save_team(team)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        ticket_id = await analyst_assignment_ticket(client)
        manager = await login(client, "rfa.manager@example.test")
        teams = await client.get("/api/v1/analyst/assignment-teams?route=rfa")
        candidates = await client.get(f"/api/v1/analyst/candidates?route=rfa&teamId={team.team_id}")
        assigned = await client.post(
            f"/api/v1/analyst/tasks/{ticket_id}/assign",
            headers={"X-CSRF-Token": str(manager["csrfToken"])},
            json={"teamId": str(team.team_id), "analystUserIds": [str(analyst.user_id)]},
        )
    assert team.team_id in {UUID(item["teamId"]) for item in teams.json()["teams"]}
    assert [item["userId"] for item in candidates.json()["analysts"]] == [str(analyst.user_id)]
    assignment = assigned.json()["assignments"][0]
    assert assignment["teamId"] == str(team.team_id)
    assert assignment["teamName"] == team.name


@pytest.mark.asyncio
async def test_candidate_api_requires_an_exact_team_id() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        await login(client, "rfa.manager@example.test")
        response = await client.get("/api/v1/analyst/candidates?route=rfa")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_cm_manager_selects_only_a_cm_assignment_team() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    analyst = app.state.access_services.repository.get_user_by_username("analyst.geo@example.test")
    assert analyst is not None
    cm_team = OrgTeam(
        team_id=uuid4(),
        name="CM Geospatial Collection Team",
        kind=TeamKind.CM,
        member_user_ids=(analyst.user_id,),
    )
    app.state.team_repository.save_team(cm_team)
    rfa_team = next(
        team for team in app.state.team_repository.list_teams() if team.kind == TeamKind.RFA
    )
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        customer = await login(client, "user@example.test")
        ticket_id = await route_assessment_ticket(client, str(customer["csrfToken"]))
        jioc = await login(client, "jioc.team@example.test")
        await client.post(
            f"/api/v1/routing/{ticket_id}/run",
            headers={"X-CSRF-Token": str(jioc["csrfToken"])},
        )
        await client.post(
            f"/api/v1/routing/{ticket_id}/approve",
            headers={"X-CSRF-Token": str(jioc["csrfToken"])},
            json={"route": "cm", "overrideReason": "Collection is required."},
        )
        customer = await login(client, "user@example.test")
        await client.post(
            f"/api/v1/tickets/{ticket_id}/collect-choice",
            headers={"X-CSRF-Token": str(customer["csrfToken"])},
            json={"analysed": False},
        )
        manager = await login(client, "collection.manager@example.test")
        catalogue = await client.get("/api/v1/analyst/assignment-teams?route=cm")
        candidates = await client.get(
            f"/api/v1/analyst/candidates?route=cm&teamId={cm_team.team_id}"
        )
        wrong_area = await client.post(
            f"/api/v1/analyst/tasks/{ticket_id}/assign",
            headers={"X-CSRF-Token": str(manager["csrfToken"])},
            json={"teamId": str(rfa_team.team_id), "analystUserIds": [str(analyst.user_id)]},
        )
        assigned = await client.post(
            f"/api/v1/analyst/tasks/{ticket_id}/assign",
            headers={"X-CSRF-Token": str(manager["csrfToken"])},
            json={"teamId": str(cm_team.team_id), "analystUserIds": [str(analyst.user_id)]},
        )
    assert cm_team.team_id in {UUID(item["teamId"]) for item in catalogue.json()["teams"]}
    assert [item["userId"] for item in candidates.json()["analysts"]] == [str(analyst.user_id)]
    assert wrong_area.status_code == 404
    assignment = assigned.json()["assignments"][0]
    assert assignment["teamId"] == str(cm_team.team_id)
    assert assignment["teamName"] == cm_team.name


def test_oversight_availability_uses_the_server_local_date(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class LocalNow:
        def astimezone(self) -> "LocalNow":
            return self

        def date(self) -> date:
            return date(2030, 2, 3)

    class FakeDateTime:
        @classmethod
        def now(cls) -> LocalNow:
            return LocalNow()

    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    captured: list[str] = []
    availability = app.state.team_availability_service
    original = availability.availability

    def record_date(team: OrgTeam, entry_date: str):
        captured.append(entry_date)
        return original(team, entry_date)

    monkeypatch.setattr("coeus.services.routing_oversight.datetime", FakeDateTime)
    monkeypatch.setattr(availability, "availability", record_date)
    jioc = app.state.access_services.repository.get_user_by_username("jioc.team@example.test")
    assert jioc is not None
    RoutingOversightService(
        app.state.ticket_services,
        app.state.team_repository,
        app.state.access_services.repository,
        availability,
    ).view(jioc)
    assert captured and set(captured) == {"2030-02-03"}
