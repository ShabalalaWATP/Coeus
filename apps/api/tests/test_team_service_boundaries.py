from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any, Never, cast
from uuid import uuid4

import pytest
from fastapi import FastAPI

from coeus.core.config import Settings
from coeus.core.errors import AppError
from coeus.core.permissions import Permission
from coeus.domain.auth import UserAccount
from coeus.domain.enums import TicketState
from coeus.domain.teams import CalendarStatus, OrgTeam, TeamCalendarEntry, TeamKind, UserProfile
from coeus.main import create_app
from coeus.persistence.state_store import StateStore
from coeus.repositories.auth import SeedUserRepository
from coeus.repositories.teams import TeamRepository
from coeus.repositories.teams_seed import seed_teams
from coeus.services.capability_catalogue import CapabilityCatalogue, _regions, _tags
from coeus.services.team_availability import (
    TeamAvailabilityService,
    can_write_entry,
    parse_iso_date,
)
from coeus.services.tickets import TicketServices


def _app() -> FastAPI:
    return create_app(Settings(environment="test", argon2_memory_cost=8_192))


def _user(app: FastAPI, username: str) -> UserAccount:
    user = app.state.access_services.repository.get_user_by_username(username)
    assert user is not None
    return cast(UserAccount, user)


def _rfa_team(app: FastAPI) -> OrgTeam:
    return cast(
        OrgTeam,
        next(team for team in app.state.team_repository.list_teams() if team.kind == TeamKind.RFA),
    )


def test_team_workspace_rejects_unknown_members_and_unshared_profiles() -> None:
    app = _app()
    service = app.state.team_workspace_service
    manager = _user(app, "rfa.manager@example.test")
    team = _rfa_team(app)

    with pytest.raises(AppError, match="Team was not found"):
        service.team_details(manager, uuid4())
    with pytest.raises(AppError, match="active accounts"):
        service.add_member(manager, team.team_id, uuid4())
    with pytest.raises(AppError, match="not a member"):
        service.remove_member(manager, team.team_id, uuid4())
    with pytest.raises(AppError, match="Profile was not found"):
        service.get_profile(manager, uuid4())


def test_team_workspace_requires_profile_permission_and_preserves_member_boundaries() -> None:
    app = _app()
    service = app.state.team_workspace_service
    manager = _user(app, "rfa.manager@example.test")
    analyst = _user(app, "analyst@example.test")
    team = _rfa_team(app)

    with pytest.raises(AppError, match="Permission denied"):
        service.update_my_profile(replace(analyst, permissions=frozenset()), "", (), "")
    assert can_write_entry(manager, team, analyst.user_id)
    assert not can_write_entry(manager, team, uuid4())
    assert not can_write_entry(analyst, team, manager.user_id)
    with pytest.raises(AppError, match="ISO calendar dates"):
        parse_iso_date("not-a-date")


def test_team_workspace_covers_full_roster_admin_and_non_manager_paths() -> None:
    app = _app()
    service = app.state.team_workspace_service
    repository = app.state.team_repository
    manager = _user(app, "rfa.manager@example.test")
    analyst = _user(app, "analyst@example.test")
    admin = _user(app, "admin@example.test")
    colleague = _user(app, "colleague@example.test")
    team = _rfa_team(app)

    repository.save_profile(UserProfile(user_id=colleague.user_id, title="Existing profile"))
    updated = service.add_member(manager, team.team_id, colleague.user_id)
    assert colleague.user_id in updated.member_user_ids
    assert repository.get_profile(colleague.user_id) is not None

    full_team = replace(team, member_user_ids=(manager.user_id, *(uuid4() for _ in range(49))))
    repository.save_team(full_team)
    with pytest.raises(AppError, match="member limit"):
        service.add_member(manager, full_team.team_id, colleague.user_id)

    repository.save_team(team)
    elevated_member = replace(analyst, permissions=analyst.permissions | {Permission.TEAM_MANAGE})
    with pytest.raises(AppError, match="Only the team's managers"):
        service.remove_member(elevated_member, full_team.team_id, full_team.member_user_ids[0])
    with pytest.raises(AppError, match="Profile was not found"):
        service.get_profile(admin, uuid4())
    assert service.list_teams(admin)


def test_seed_profiles_are_personal_and_preserve_user_edits() -> None:
    app = _app()
    repository = app.state.team_repository
    users = cast(SeedUserRepository, app.state.team_workspace_service._users)
    analyst = _user(app, "analyst.2@example.test")

    seeded = repository.get_profile(analyst.user_id)
    assert seeded is not None
    assert seeded.title == "Military Intelligence Analyst"
    assert seeded.specialisms
    assert seeded.bio

    edited = replace(seeded, title="Custom title", specialisms=("OSINT",), bio="My own bio.")
    repository.save_profile(edited)
    seed_teams(repository, users)
    assert repository.get_profile(analyst.user_id) == edited

    bare = UserProfile(user_id=analyst.user_id, title=analyst.display_name)
    repository.save_profile(bare)
    seed_teams(repository, users)
    assert repository.get_profile(analyst.user_id) == bare


def test_seed_profiles_give_unlisted_users_a_default_profile() -> None:
    app = _app()
    repository = app.state.team_repository
    extra = UserAccount(
        user_id=uuid4(),
        username="extra@example.test",
        display_name="Extra User",
        roles=frozenset(),
        permissions=frozenset(),
        password_hash="",
        is_active=True,
        clearance_level=1,
    )
    users = cast(SeedUserRepository, SimpleNamespace(list_users=lambda: (extra,)))

    seed_teams(repository, users)
    created = repository.get_profile(extra.user_id)
    assert created is not None
    assert created.title == "Extra User"

    seed_teams(repository, users)
    assert repository.get_profile(extra.user_id) == created


def test_calendar_audit_failures_restore_the_previous_repository_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _app()
    calendar = app.state.team_calendar_service
    repository = app.state.team_repository
    manager = _user(app, "rfa.manager@example.test")
    team = _rfa_team(app)
    first_date = (datetime.now(UTC).date() + timedelta(days=1)).isoformat()
    second_date = (datetime.now(UTC).date() + timedelta(days=2)).isoformat()

    monkeypatch.setattr(calendar._audit_log, "record", _fail_audit)
    with pytest.raises(RuntimeError, match="audit unavailable"):
        calendar.add_entry(
            manager,
            team,
            manager.user_id,
            first_date,
            CalendarStatus.LEAVE,
            "Leave",
        )
    assert repository.list_entries(team.team_id) == ()

    monkeypatch.setattr(calendar._audit_log, "record", _record_audit)
    entry = calendar.add_entry(
        manager,
        team,
        manager.user_id,
        second_date,
        CalendarStatus.ON_TASK,
        "Task",
    )
    monkeypatch.setattr(calendar._audit_log, "record", _fail_audit)
    with pytest.raises(RuntimeError, match="audit unavailable"):
        calendar.remove_entry(manager, team, entry.entry_id)
    assert repository.get_entry(entry.entry_id) == entry


class _FailingStateStore(StateStore):
    def load(self, namespace: str) -> dict[str, Any] | None:
        return None

    def save(self, namespace: str, payload: dict[str, Any]) -> Never:
        raise RuntimeError(f"failed {namespace}")


def _team() -> OrgTeam:
    return OrgTeam(
        team_id=uuid4(),
        name="Test team",
        kind=TeamKind.RFA,
        manager_user_ids=(uuid4(),),
        member_user_ids=(uuid4(),),
    )


def test_team_repository_rolls_back_each_persisted_record_kind() -> None:
    repository = TeamRepository(_FailingStateStore())
    team = _team()
    entry = TeamCalendarEntry(
        entry_id=uuid4(),
        team_id=team.team_id,
        user_id=team.member_user_ids[0],
        entry_date="2026-07-20",
        status=CalendarStatus.LEAVE,
        note="Leave",
    )
    profile = UserProfile(user_id=team.member_user_ids[0], title="Analyst")

    with pytest.raises(RuntimeError, match="teams"):
        repository.save_team(team)
    with pytest.raises(RuntimeError, match="team_calendar"):
        repository.save_entry(entry)
    with pytest.raises(RuntimeError, match="user_profiles"):
        repository.save_profile(profile)

    assert repository.list_teams() == ()
    assert repository.list_entries(team.team_id) == ()
    assert repository.get_profile(profile.user_id) is None


def test_team_repository_handles_memory_only_and_missing_calendar_entries() -> None:
    repository = TeamRepository()
    team = _team()

    repository.save_team(team)

    assert repository.get_team(team.team_id) == team
    assert repository.delete_entry(uuid4()) is None


def test_team_availability_ignores_assignments_outside_the_team() -> None:
    member = uuid4()
    foreign_assignment = SimpleNamespace(active=True, analyst_user_id=uuid4())
    ticket = SimpleNamespace(
        state=TicketState.ANALYST_IN_PROGRESS,
        analyst_assignments=(foreign_assignment,),
    )
    tickets = cast(
        TicketServices,
        SimpleNamespace(tickets=SimpleNamespace(assignment_snapshot=lambda: (ticket,))),
    )

    assert (
        TeamAvailabilityService(TeamRepository(), tickets)._assigned_members(frozenset({member}))
        == set()
    )


def test_catalogue_fallbacks_cover_missing_catalogue_records() -> None:
    catalogue = CapabilityCatalogue()
    assert _tags("  ") == frozenset()
    assert _regions("") == frozenset()

    rfa_id = catalogue.recommend_rfa(frozenset({"maritime"}))[0].team_id
    catalogue._by_id.pop(rfa_id)
    assert catalogue.best_rfa_team(frozenset({"maritime"})).team_id == "RFA-GENERAL"

    cm_id = catalogue.recommend_cm(frozenset({"imagery"}))[0].team_id
    catalogue._by_id.pop(cm_id)
    assert catalogue.best_cm_team(frozenset({"imagery"})) is None


def _record_audit(*_args: object, **_kwargs: object) -> None:
    return None


def _fail_audit(*_args: object, **_kwargs: object) -> Never:
    raise RuntimeError("audit unavailable")
