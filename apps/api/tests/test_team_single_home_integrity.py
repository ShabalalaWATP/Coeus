from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime
from threading import Barrier
from typing import cast
from uuid import uuid4

import pytest

from coeus.core.errors import AppError
from coeus.domain.auth import RoleName, UserAccount
from coeus.domain.teams import OrgTeam, TeamKind
from coeus.repositories.access import SeedAccessRepository
from coeus.repositories.auth import SeedUserRepository
from coeus.services.team_availability import active_team_ids_for_user
from test_team_service_boundaries import _app, _rfa_team, _user


def test_team_workspace_rejects_second_home_and_limits_candidate_results() -> None:
    app = _app()
    service = app.state.team_workspace_service
    repository = cast(SeedUserRepository, service._users)
    manager = _user(app, "rfa.manager@example.test")
    rfa_team = _rfa_team(app)
    cm_analyst = _user(app, "analyst.3@example.test")
    with pytest.raises(AppError, match="another active team"):
        service.add_member(manager, rfa_team.team_id, cm_analyst.user_id)
    assert cm_analyst not in service.member_candidates(manager, rfa_team.team_id, "analyst.3")
    for index in range(12):
        repository.save(
            UserAccount(
                user_id=uuid4(),
                username=f"candidate-{index:02d}@example.test",
                display_name=f"Candidate {index:02d}",
                roles=frozenset(),
                permissions=frozenset(),
                password_hash="",
                is_active=True,
                clearance_level=1,
            )
        )
    assert len(service.member_candidates(manager, rfa_team.team_id, "candidate")) == 10


def test_concurrent_member_add_preserves_one_active_home_team() -> None:
    app = _app()
    service = app.state.team_workspace_service
    admin = _user(app, "admin@example.test")
    colleague = _user(app, "colleague@example.test")
    route_teams = [
        team
        for team in app.state.team_repository.list_teams()
        if team.name in {"RFA Assessment Team", "Collection Management Team"}
    ]
    assert {team.kind for team in route_teams} == {TeamKind.RFA, TeamKind.CM}
    barrier = Barrier(2)

    def add(team: OrgTeam) -> OrgTeam:
        barrier.wait()
        return service.add_member(admin, team.team_id, colleague.user_id)

    successes = 0
    conflicts = 0
    with ThreadPoolExecutor(max_workers=2) as executor:
        for future in [executor.submit(add, team) for team in route_teams]:
            try:
                future.result()
                successes += 1
            except AppError as error:
                assert error.code == "active_team_membership_exists"
                conflicts += 1
    assert (successes, conflicts) == (1, 1)
    memberships = active_team_ids_for_user(app.state.team_repository, colleague.user_id)
    assert len(memberships) == 1


def test_availability_reports_inactive_roster_people_without_counting_them() -> None:
    app = _app()
    team = _rfa_team(app)
    disabled = _user(app, "disabled@example.test")
    team = replace(team, member_user_ids=(*team.member_user_ids, disabled.user_id))
    app.state.team_repository.save_team(team)
    today = datetime.now(UTC).date().isoformat()
    availability = app.state.team_availability_service.availability(team, today)
    assert availability.members == 6
    assert availability.active_people == 5
    assert availability.assignable == 3


def test_manager_with_analyst_role_does_not_manufacture_delivery_capacity() -> None:
    app = _app()
    team = _rfa_team(app)
    manager = _user(app, "rfa.manager@example.test")
    access = cast(SeedAccessRepository, app.state.team_availability_service._users)
    users = cast(SeedUserRepository, access._users)
    users.save(replace(manager, roles=manager.roles | {RoleName.INTELLIGENCE_ANALYST}))

    availability = app.state.team_availability_service.availability(
        team, datetime.now(UTC).date().isoformat()
    )

    assert availability.assignable == 3
