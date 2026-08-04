"""Analyst and team resolution rules behind an assignment."""

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from coeus.core.errors import AppError
from coeus.domain.auth import Permission, RoleName
from coeus.domain.enums import TicketState
from coeus.domain.teams import OrgTeam, TeamKind
from coeus.domain.tickets import AnalystAssignment, IntakeDetails, RoutingRoute, TicketRecord
from coeus.services.analyst_assignment_service import (
    MAX_ANALYSTS_PER_ASSIGNMENT,
    AnalystAssignmentService,
)

TEAM_ID, OTHER_TEAM = uuid4(), uuid4()
MANAGER, ANALYST = uuid4(), uuid4()


class _Access:
    def __init__(self, accounts: dict[UUID, SimpleNamespace]) -> None:
        self._accounts = accounts

    def get_user(self, user_id: UUID) -> SimpleNamespace | None:
        return self._accounts.get(user_id)


class _Teams:
    def __init__(self, teams: dict[UUID, OrgTeam]) -> None:
        self._teams = teams

    def get_team(self, team_id: UUID) -> OrgTeam | None:
        return self._teams.get(team_id)

    def list_teams(self) -> tuple[OrgTeam, ...]:
        return tuple(self._teams.values())


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


def _account(user_id: UUID, *, active: bool = True, analyst: bool = True) -> SimpleNamespace:
    return SimpleNamespace(
        user_id=user_id,
        display_name="Synthetic Analyst",
        is_active=active,
        roles=(RoleName.INTELLIGENCE_ANALYST,) if analyst else (),
    )


def _actor(*permissions: Permission) -> SimpleNamespace:
    return SimpleNamespace(user_id=MANAGER, permissions=set(permissions))


def _service(
    accounts: dict[UUID, SimpleNamespace] | None = None,
    teams: dict[UUID, OrgTeam] | None = None,
) -> AnalystAssignmentService:
    return AnalystAssignmentService(
        SimpleNamespace(),  # type: ignore[arg-type]
        _Access(accounts if accounts is not None else {ANALYST: _account(ANALYST)}),  # type: ignore[arg-type]
        _Teams(teams if teams is not None else {TEAM_ID: _team()}),  # type: ignore[arg-type]
        SimpleNamespace(),  # type: ignore[arg-type]
        SimpleNamespace(),  # type: ignore[arg-type]
    )


def _ticket(*assignments: AnalystAssignment) -> TicketRecord:
    return TicketRecord(
        uuid4(),
        "TCK-0001",
        uuid4(),
        TicketState.ANALYST_IN_PROGRESS,
        IntakeDetails(title="Synthetic"),
        analyst_assignments=assignments,
    )


def _assignment(team_id: UUID | None) -> AnalystAssignment:
    return AnalystAssignment(
        uuid4(),
        uuid4(),
        ANALYST,
        MANAGER,
        RoutingRoute.RFA,
        datetime(2026, 8, 4, tzinfo=UTC),
        team_id=team_id,
    )


def test_a_distinct_bounded_analyst_list_is_required() -> None:
    service = _service()

    with pytest.raises(AppError) as empty:
        service._resolve_analysts(())
    with pytest.raises(AppError) as too_many:
        service._resolve_analysts(tuple(uuid4() for _ in range(MAX_ANALYSTS_PER_ASSIGNMENT + 1)))

    assert empty.value.code == "invalid_analyst"
    assert too_many.value.code == "invalid_analyst"


def test_repeated_identifiers_collapse_to_one_analyst() -> None:
    service = _service()

    assert service._resolve_analysts((ANALYST, ANALYST)) == (
        service._resolve_analysts((ANALYST,))[0],
    )


@pytest.mark.parametrize(
    "accounts",
    [
        {},
        {ANALYST: _account(ANALYST, active=False)},
        {ANALYST: _account(ANALYST, analyst=False)},
    ],
)
def test_an_unknown_inactive_or_non_analyst_account_is_refused(
    accounts: dict[UUID, SimpleNamespace],
) -> None:
    service = _service(accounts)

    with pytest.raises(AppError) as error:
        service._resolve_analysts((ANALYST,))

    assert error.value.code == "invalid_analyst"
    assert error.value.status_code == 422


@pytest.mark.parametrize(
    "assignments",
    [(), (_assignment(TEAM_ID), _assignment(OTHER_TEAM)), (_assignment(None),)],
)
def test_reassignment_needs_exactly_one_identifiable_current_team(
    assignments: tuple[AnalystAssignment, ...],
) -> None:
    service = _service()

    with pytest.raises(AppError) as error:
        service._reassignment_team_id(_actor(), _ticket(*assignments), RoutingRoute.RFA)

    assert error.value.code == "assignment_team_ambiguous"


@pytest.mark.parametrize(
    "teams",
    [
        {},
        {TEAM_ID: _team(is_active=False)},
        {TEAM_ID: _team(kind=TeamKind.CM)},
    ],
)
def test_reassignment_refuses_a_missing_closed_or_mismatched_team(
    teams: dict[UUID, OrgTeam],
) -> None:
    service = _service(teams=teams)

    with pytest.raises(AppError) as error:
        service._reassignment_team_id(_actor(), _ticket(_assignment(TEAM_ID)), RoutingRoute.RFA)

    assert error.value.code == "assignment_team_unavailable"


def test_only_a_manager_of_the_current_team_or_a_role_administrator_may_reassign() -> None:
    service = _service()
    ticket = _ticket(_assignment(TEAM_ID))

    assert service._reassignment_team_id(_actor(), ticket, RoutingRoute.RFA) == TEAM_ID

    outsider = SimpleNamespace(user_id=uuid4(), permissions=set())
    with pytest.raises(AppError) as error:
        service._reassignment_team_id(outsider, ticket, RoutingRoute.RFA)  # type: ignore[arg-type]
    assert error.value.code == "reassignment_team_forbidden"

    administrator = SimpleNamespace(user_id=uuid4(), permissions={Permission.ROLE_MANAGE})
    assert (
        service._reassignment_team_id(administrator, ticket, RoutingRoute.RFA)  # type: ignore[arg-type]
        == TEAM_ID
    )
