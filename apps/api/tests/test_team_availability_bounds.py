"""Team-scoped availability windows and single-home capacity eligibility."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from coeus.core.errors import AppError
from coeus.domain.auth import Permission, RoleName
from coeus.domain.teams import CalendarStatus, OrgTeam, TeamKind
from coeus.services.team_availability import (
    MANAGER_ROLE_BY_TEAM_KIND,
    MAX_CALENDAR_WINDOW_DAYS,
    TeamAvailabilityService,
    TeamCalendarService,
)

TEAM_ID, OTHER_TEAM = uuid4(), uuid4()
MANAGER, ANALYST = uuid4(), uuid4()
TODAY = datetime.now(UTC).date()


class _Teams:
    def __init__(self, teams: tuple[OrgTeam, ...]) -> None:
        self._teams = {team.team_id: team for team in teams}
        self.saved: list[object] = []

    def get_team(self, team_id: UUID) -> OrgTeam | None:
        return self._teams.get(team_id)

    def list_teams(self) -> tuple[OrgTeam, ...]:
        return tuple(self._teams.values())

    def save_entry(self, entry: object) -> None:
        self.saved.append(entry)


class _Users:
    def __init__(self, users: tuple[SimpleNamespace, ...]) -> None:
        self._users = users

    def list_users(self) -> tuple[SimpleNamespace, ...]:
        return self._users


def _team(team_id: UUID = TEAM_ID, **overrides: object) -> OrgTeam:
    values: dict[str, object] = {
        "team_id": team_id,
        "name": "RFA Assessment Team",
        "kind": TeamKind.RFA,
        "manager_user_ids": (MANAGER,),
        "member_user_ids": (ANALYST,),
        "is_active": True,
    }
    values.update(overrides)
    return OrgTeam(**values)  # type: ignore[arg-type]


def _analyst(user_id: UUID = ANALYST, *, active: bool = True) -> SimpleNamespace:
    return SimpleNamespace(
        user_id=user_id,
        is_active=active,
        roles=(RoleName.INTELLIGENCE_ANALYST,),
        permissions=set(),
    )


def _service(teams: tuple[OrgTeam, ...], users: tuple[SimpleNamespace, ...]):  # type: ignore[no-untyped-def]
    return TeamAvailabilityService(
        _Teams(teams),  # type: ignore[arg-type]
        SimpleNamespace(),  # type: ignore[arg-type]
        _Users(users),  # type: ignore[arg-type]
    )


def _calendar(teams: tuple[OrgTeam, ...]):  # type: ignore[no-untyped-def]
    return TeamCalendarService(
        _Teams(teams),  # type: ignore[arg-type]
        SimpleNamespace(record=lambda *_args: None),  # type: ignore[arg-type]
    )


def test_a_closed_team_offers_no_assignable_capacity() -> None:
    service = _service((_team(is_active=False),), (_analyst(),))

    assert service.assignable_member_ids(_team(is_active=False)) == frozenset()


def test_only_a_single_home_active_analyst_adds_capacity() -> None:
    service = _service((_team(),), (_analyst(),))

    assert service.assignable_member_ids(_team()) == frozenset({ANALYST})


def test_an_inactive_account_or_a_manager_never_adds_capacity() -> None:
    inactive = _service((_team(),), (_analyst(active=False),))
    assert inactive.assignable_member_ids(_team()) == frozenset()

    managing = _team(manager_user_ids=(MANAGER, ANALYST))
    assert _service((managing,), (_analyst(),)).assignable_member_ids(managing) == frozenset()


def test_an_overlapping_second_posting_fails_closed() -> None:
    second = _team(OTHER_TEAM, name="Collection Team", kind=TeamKind.CM)
    service = _service((_team(), second), (_analyst(),))

    assert service.assignable_member_ids(_team()) == frozenset()


def _actor() -> SimpleNamespace:
    return SimpleNamespace(
        user_id=MANAGER,
        permissions={Permission.TEAM_MANAGE},
        roles=(MANAGER_ROLE_BY_TEAM_KIND[TeamKind.RFA],),
        is_active=True,
    )


def _add(service, **overrides):  # type: ignore[no-untyped-def]
    values: dict[str, object] = {
        "actor": _actor(),
        "team": _team(),
        "target_user_id": ANALYST,
        "entry_date": TODAY.isoformat(),
        "status": CalendarStatus.LEAVE,
        "note": "Annual leave.",
        "end_date": "",
    }
    values.update(overrides)
    return service.add_entry(**values)


def test_an_entry_for_an_unknown_or_closed_team_is_not_found() -> None:
    with pytest.raises(AppError) as missing:
        _add(_calendar(()))
    assert missing.value.code == "team_not_found"

    with pytest.raises(AppError) as closed:
        _add(_calendar((_team(is_active=False),)))
    assert closed.value.code == "team_not_found"


def test_an_end_date_before_the_start_is_refused() -> None:
    service = _calendar((_team(),))

    with pytest.raises(AppError) as error:
        _add(service, end_date=(TODAY - timedelta(days=1)).isoformat())

    assert error.value.code == "invalid_calendar_date"


def test_a_past_entry_is_refused() -> None:
    service = _calendar((_team(),))

    with pytest.raises(AppError) as error:
        _add(service, entry_date=(TODAY - timedelta(days=1)).isoformat())

    assert error.value.code == "invalid_calendar_date"


def test_an_entry_beyond_the_planning_window_is_refused() -> None:
    service = _calendar((_team(),))
    beyond = TODAY + timedelta(days=MAX_CALENDAR_WINDOW_DAYS + 1)

    with pytest.raises(AppError) as error:
        _add(service, end_date=beyond.isoformat())

    assert error.value.code == "invalid_calendar_date"


def test_a_single_day_entry_records_no_separate_end_date() -> None:
    service = _calendar((_team(),))

    entry = _add(service, end_date=TODAY.isoformat())

    assert entry.end_date == ""
    assert entry.entry_date == TODAY.isoformat()
