"""Deterministic single-process workforce authority race regressions."""

import asyncio
from datetime import UTC, datetime
from threading import Event
from uuid import UUID

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from coeus.core.config import Settings
from coeus.core.errors import AppError
from coeus.domain.auth import UserAccount
from coeus.domain.teams import CalendarStatus, OrgTeam
from coeus.main import create_app
from routing_helpers import analyst_assignment_ticket


def _app() -> FastAPI:
    return create_app(Settings(environment="test", argon2_memory_cost=8_192))


def _user(app: FastAPI, username: str) -> UserAccount:
    user = app.state.access_services.repository.get_user_by_username(username)
    assert user is not None
    return user


def _rfa_team(app: FastAPI) -> OrgTeam:
    return next(
        team
        for team in app.state.team_repository.list_teams()
        if team.name == "RFA Assessment Team"
    )


def _assignment_attempt(
    app: FastAPI,
    manager: UserAccount,
    analyst: UserAccount,
    team: OrgTeam,
    ticket_id: str,
    started: Event,
) -> str:
    started.set()
    try:
        app.state.analyst_assignment_service.assign(
            manager,
            UUID(ticket_id),
            (analyst.user_id,),
            (),
            team.team_id,
        )
    except AppError as error:
        return error.code
    return "assigned"


async def _ticket(app: FastAPI) -> str:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        return await analyst_assignment_ticket(client)


@pytest.mark.asyncio
async def test_roster_removal_finishes_before_waiting_assignment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _app()
    ticket_id = await _ticket(app)
    manager = _user(app, "rfa.manager@example.test")
    analyst = _user(app, "analyst.2@example.test")
    team = _rfa_team(app)
    workspace = app.state.team_workspace_service
    mutation_applied = Event()
    release = Event()
    assignment_started = Event()
    original = workspace._save_team_with_audit

    def gated_save(*args: object, **kwargs: object) -> None:
        original(*args, **kwargs)
        mutation_applied.set()
        assert release.wait(5)

    monkeypatch.setattr(workspace, "_save_team_with_audit", gated_save)
    removal = asyncio.create_task(
        asyncio.to_thread(workspace.remove_member, manager, team.team_id, analyst.user_id)
    )
    assert await asyncio.to_thread(mutation_applied.wait, 5)
    assignment = asyncio.create_task(
        asyncio.to_thread(
            _assignment_attempt,
            app,
            manager,
            analyst,
            team,
            ticket_id,
            assignment_started,
        )
    )
    assert await asyncio.to_thread(assignment_started.wait, 5)
    release.set()

    await removal
    assert await assignment == "analyst_outside_team"


@pytest.mark.asyncio
async def test_deactivation_finishes_before_waiting_assignment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _app()
    ticket_id = await _ticket(app)
    manager = _user(app, "rfa.manager@example.test")
    analyst = _user(app, "analyst.2@example.test")
    admin = _user(app, "admin@example.test")
    team = _rfa_team(app)
    users = app.state.user_admin_service
    mutation_applied = Event()
    release = Event()
    assignment_started = Event()
    original = users._apply_and_audit

    def gated_apply(*args: object, **kwargs: object) -> None:
        original(*args, **kwargs)
        mutation_applied.set()
        assert release.wait(5)

    monkeypatch.setattr(users, "_apply_and_audit", gated_apply)
    deactivation = asyncio.create_task(
        asyncio.to_thread(users.set_active, admin, analyst.user_id, False)
    )
    assert await asyncio.to_thread(mutation_applied.wait, 5)
    assignment = asyncio.create_task(
        asyncio.to_thread(
            _assignment_attempt,
            app,
            manager,
            analyst,
            team,
            ticket_id,
            assignment_started,
        )
    )
    assert await asyncio.to_thread(assignment_started.wait, 5)
    release.set()

    await deactivation
    assert await assignment == "invalid_analyst"


@pytest.mark.asyncio
async def test_calendar_block_finishes_before_waiting_assignment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _app()
    ticket_id = await _ticket(app)
    manager = _user(app, "rfa.manager@example.test")
    analyst = _user(app, "analyst.2@example.test")
    team = _rfa_team(app)
    calendar = app.state.team_calendar_service
    mutation_applied = Event()
    release = Event()
    assignment_started = Event()
    original = app.state.team_repository.save_entry

    def gated_save(entry: object) -> None:
        original(entry)
        mutation_applied.set()
        assert release.wait(5)

    monkeypatch.setattr(app.state.team_repository, "save_entry", gated_save)
    calendar_write = asyncio.create_task(
        asyncio.to_thread(
            calendar.add_entry,
            manager,
            team,
            analyst.user_id,
            datetime.now(UTC).date().isoformat(),
            CalendarStatus.LEAVE,
            "Leave",
        )
    )
    assert await asyncio.to_thread(mutation_applied.wait, 5)
    assignment = asyncio.create_task(
        asyncio.to_thread(
            _assignment_attempt,
            app,
            manager,
            analyst,
            team,
            ticket_id,
            assignment_started,
        )
    )
    assert await asyncio.to_thread(assignment_started.wait, 5)
    release.set()

    await calendar_write
    assert await assignment == "analyst_unavailable"
