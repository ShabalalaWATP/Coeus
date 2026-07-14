from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import uuid4

import pytest
from fastapi import FastAPI

from coeus.core.config import Settings
from coeus.core.errors import AppError
from coeus.domain.auth import UserAccount
from coeus.domain.enums import TicketState
from coeus.domain.teams import CalendarStatus, OrgTeam, TeamKind
from coeus.domain.tickets import (
    AnalystAssignment,
    IntakeDetails,
    ManagerRoutingDecision,
    ManagerRoutingDecisionStatus,
    RoutingRoute,
    TicketRecord,
)
from coeus.main import create_app
from coeus.services.analyst_assignment_service import AnalystAssignmentService


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


def _fail_audit(*_args: object, **_kwargs: object) -> None:
    raise RuntimeError("audit unavailable")


def test_manager_candidate_search_and_profile_audit_rollback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _app()
    service = app.state.team_workspace_service
    repository = app.state.team_repository
    manager = _user(app, "rfa.manager@example.test")
    customer = _user(app, "user@example.test")
    team = _rfa_team(app)
    assert service.member_candidates(manager, team.team_id, "coll")
    assert service.member_candidates(manager, team.team_id, "ab") == ()
    assert service.member_candidates(manager, team.team_id, "no-such-user") == ()
    with pytest.raises(AppError, match="Permission denied"):
        service.member_candidates(customer, team.team_id, "coll")
    original = repository.get_profile(manager.user_id)
    assert original is not None
    monkeypatch.setattr(service._audit_log, "record", _fail_audit)
    with pytest.raises(RuntimeError, match="audit unavailable"):
        service.update_my_profile(manager, "Changed", (), "")
    assert repository.get_profile(manager.user_id) == original
    repository.delete_profile(manager.user_id)
    assert repository.delete_profile(manager.user_id) is None
    with pytest.raises(RuntimeError, match="audit unavailable"):
        service.update_my_profile(manager, "Changed", (), "")
    assert repository.get_profile(manager.user_id) is None


def test_assignment_candidates_and_state_boundaries(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _app()
    service: AnalystAssignmentService = app.state.analyst_assignment_service
    manager = _user(app, "rfa.manager@example.test")
    customer = _user(app, "user@example.test")
    admin = _user(app, "admin@example.test")
    with pytest.raises(AppError, match="Permission denied"):
        service.analyst_candidates(customer, RoutingRoute.RFA)
    assert service.analyst_candidates(manager, RoutingRoute.RFA)
    assert service.analyst_candidates(admin, RoutingRoute.RFA)
    assert service.analyst_candidates(admin, RoutingRoute.CM)
    with pytest.raises(AppError, match="Permission denied"):
        service.analyst_candidates(manager, RoutingRoute.CM)
    with pytest.raises(AppError, match="one and five"):
        service._resolve_analysts(())
    with pytest.raises(AppError, match="active analyst"):
        service._resolve_analysts((uuid4(),))
    sample = TicketRecord(
        uuid4(), "TKT-BOUNDARY", customer.user_id, TicketState.ANALYST_ASSIGNMENT, IntakeDetails()
    )
    monkeypatch.setattr(
        service._tickets.tickets,
        "get_workflow_ticket",
        lambda *_a, **_k: replace(sample, state=TicketState.CLOSED_DELIVERED),
    )
    with pytest.raises(AppError, match="awaiting assignment"):
        service.assign(manager, sample.ticket_id, (manager.user_id,), ())
    monkeypatch.setattr(service._tickets.tickets, "get_workflow_ticket", lambda *_a, **_k: sample)
    with pytest.raises(AppError, match="no approved route"):
        service.assign(manager, sample.ticket_id, (manager.user_id,), ())
    decision = ManagerRoutingDecision(
        uuid4(),
        sample.ticket_id,
        RoutingRoute.RFA,
        ManagerRoutingDecisionStatus.APPROVED,
        "Approved",
        None,
        manager.user_id,
        datetime.now(UTC),
    )
    assignment = AnalystAssignment(
        uuid4(),
        sample.ticket_id,
        _user(app, "analyst@example.test").user_id,
        manager.user_id,
        RoutingRoute.RFA,
        datetime.now(UTC),
    )
    monkeypatch.setattr(
        service._tickets.tickets,
        "get_workflow_ticket",
        lambda *_a, **_k: replace(
            sample, manager_decisions=(decision,), analyst_assignments=(assignment,)
        ),
    )
    with pytest.raises(AppError, match="already has"):
        service.assign(manager, sample.ticket_id, (assignment.analyst_user_id,), ())
    cm_manager = _user(app, "collection.manager@example.test")
    cm_decision = replace(decision, route=RoutingRoute.CM, actor_user_id=cm_manager.user_id)
    monkeypatch.setattr(
        service._tickets.tickets,
        "get_workflow_ticket",
        lambda *_a, **_k: replace(sample, manager_decisions=(cm_decision,)),
    )
    with pytest.raises(AppError, match="route team"):
        service.assign(
            cm_manager, sample.ticket_id, (_user(app, "analyst.4@example.test").user_id,), ()
        )


def test_assignment_permission_and_transition_guards() -> None:
    app = _app()
    service: AnalystAssignmentService = app.state.analyst_assignment_service
    rfa_manager = _user(app, "rfa.manager@example.test")

    with pytest.raises(AppError, match="Permission denied"):
        service._require_assignment_permission(rfa_manager, RoutingRoute.CM)
    with pytest.raises(AppError, match="cannot move"):
        service._ensure_transition(TicketState.CLOSED_DELIVERED, TicketState.ANALYST_IN_PROGRESS)


def test_calendar_rejects_dates_outside_the_supported_window() -> None:
    app = _app()
    calendar = app.state.team_calendar_service
    manager = _user(app, "rfa.manager@example.test")
    team = _rfa_team(app)
    for entry_date in (
        datetime.now(UTC).date() - timedelta(days=1),
        datetime.now(UTC).date() + timedelta(days=63),
    ):
        with pytest.raises(AppError, match=r"past|within the next"):
            calendar.add_entry(
                manager, team, manager.user_id, entry_date.isoformat(), CalendarStatus.AVAILABLE, ""
            )
