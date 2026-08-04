import asyncio
from dataclasses import replace
from threading import Barrier
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from coeus.core.errors import AppError
from coeus.domain.teams import OrgTeam, TeamKind
from test_manager_approval_api import _analyst_ids, _app, _assign, analyst_assignment_ticket


@pytest.mark.asyncio
async def test_cross_team_manager_cannot_take_over_an_active_assignment() -> None:
    app = _app()
    access = app.state.access_services.repository
    original_manager = access.get_user_by_username("rfa.manager@example.test")
    other_manager = access.get_user_by_username("collection.manager@example.test")
    admin = access.get_user_by_username("admin@example.test")
    replacement = access.get_user_by_username("analyst.4@example.test")
    assert original_manager is not None
    assert other_manager is not None
    assert admin is not None
    assert replacement is not None
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        ticket_id = await analyst_assignment_ticket(client)
        initial = await _assign(client, ticket_id, _analyst_ids(app, "analyst@example.test"))
    assert initial.status_code == 200
    original_team = next(
        team
        for team in app.state.team_repository.list_teams()
        if team.name == "RFA Assessment Team"
    )
    app.state.team_repository.save_team(
        replace(
            original_team,
            member_user_ids=tuple(
                user_id
                for user_id in original_team.member_user_ids
                if user_id != replacement.user_id
            ),
        )
    )
    attacker = replace(
        other_manager,
        roles=original_manager.roles,
        permissions=original_manager.permissions,
    )
    other_team = OrgTeam(
        team_id=uuid4(),
        name="Second RFA Team",
        kind=TeamKind.RFA,
        manager_user_ids=(attacker.user_id,),
        member_user_ids=(replacement.user_id,),
    )
    app.state.team_repository.save_team(other_team)
    with pytest.raises(AppError) as denied:
        app.state.analyst_assignment_service.assign(
            attacker,
            UUID(ticket_id),
            (replacement.user_id,),
            (),
            other_team.team_id,
        )
    assert denied.value.code == "reassignment_team_forbidden"
    reassigned = app.state.analyst_assignment_service.assign(
        admin,
        UUID(ticket_id),
        (replacement.user_id,),
        (),
        other_team.team_id,
    )
    active = [assignment for assignment in reassigned.analyst_assignments if assignment.active]
    assert {assignment.team_id for assignment in active} == {other_team.team_id}


@pytest.mark.asyncio
async def test_concurrent_ticket_assignment_cannot_overbook_one_analyst() -> None:
    app = _app()
    manager = app.state.access_services.repository.get_user_by_username("rfa.manager@example.test")
    analyst = app.state.access_services.repository.get_user_by_username("analyst@example.test")
    assert manager is not None and analyst is not None
    team = next(
        team
        for team in app.state.team_repository.list_teams()
        if team.name == "RFA Assessment Team"
    )
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        ticket_ids = (
            await analyst_assignment_ticket(client),
            await analyst_assignment_ticket(client),
        )
    barrier = Barrier(2)

    def attempt(ticket_id: str) -> str:
        barrier.wait()
        try:
            app.state.analyst_assignment_service.assign(
                manager, UUID(ticket_id), (analyst.user_id,), (), team.team_id
            )
        except AppError as error:
            return error.code
        return "assigned"

    outcomes = await asyncio.gather(
        asyncio.to_thread(attempt, ticket_ids[0]),
        asyncio.to_thread(attempt, ticket_ids[1]),
    )
    assert sorted(outcomes) == ["analyst_unavailable", "assigned"]
