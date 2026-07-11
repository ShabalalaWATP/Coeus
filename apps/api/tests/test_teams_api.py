from typing import Any
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from coeus.core.config import Settings
from coeus.domain.teams import (
    CalendarStatus,
    OrgTeam,
    TeamCalendarEntry,
    TeamKind,
    UserProfile,
)
from coeus.main import create_app
from coeus.persistence.codec import decode_value, encode_value
from rfi_search_helpers import login
from routing_helpers import analyst_assignment_ticket


def _app() -> FastAPI:
    return create_app(Settings(environment="test", argon2_memory_cost=8_192))


async def _team_id(client: AsyncClient, name: str) -> str:
    teams = await client.get("/api/v1/teams")
    assert teams.status_code == 200
    return next(team["id"] for team in teams.json()["teams"] if team["name"] == name)


def _user_id(app: FastAPI, username: str) -> str:
    user = app.state.access_services.repository.get_user_by_username(username)
    assert user is not None
    return str(user.user_id)


@pytest.mark.asyncio
async def test_teams_are_visible_only_to_their_own_people() -> None:
    app = _app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        await login(client, "rfa.manager@example.test")
        manager_view = await client.get("/api/v1/teams")
        team_names = [team["name"] for team in manager_view.json()["teams"]]
        assert team_names == ["RFA Assessment Team"]
        roster = manager_view.json()["teams"][0]["members"]
        manager_row = next(m for m in roster if m["username"] == "rfa.manager@example.test")
        assert manager_row["isManager"] is True
        assert any(m["username"] == "analyst@example.test" for m in roster)

        # The shared analyst sits on both the RFA and CM teams.
        await login(client, "analyst@example.test")
        analyst_view = await client.get("/api/v1/teams")
        analyst_names = {team["name"] for team in analyst_view.json()["teams"]}
        assert analyst_names == {"RFA Assessment Team", "Collection Management Team"}

        # Customers are on no team and see nothing.
        await login(client, "user@example.test")
        customer_view = await client.get("/api/v1/teams")
        assert customer_view.json()["teams"] == []


@pytest.mark.asyncio
async def test_only_the_owning_manager_changes_the_roster() -> None:
    app = _app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        manager = await login(client, "rfa.manager@example.test")
        team_id = await _team_id(client, "RFA Assessment Team")
        new_member = _user_id(app, "colleague@example.test")

        candidates = await client.get(f"/api/v1/teams/{team_id}/member-candidates?query=coll")
        assert candidates.status_code == 200
        assert candidates.json()["users"][0]["userId"] == new_member

        added = await client.post(
            f"/api/v1/teams/{team_id}/members",
            headers={"X-CSRF-Token": str(manager["csrfToken"])},
            json={"userId": new_member},
        )
        assert added.status_code == 200
        assert any(m["userId"] == new_member for m in added.json()["members"])
        repeat = await client.post(
            f"/api/v1/teams/{team_id}/members",
            headers={"X-CSRF-Token": str(manager["csrfToken"])},
            json={"userId": new_member},
        )
        assert repeat.status_code == 409

        # A member without TEAM_MANAGE cannot change the roster.
        analyst = await login(client, "analyst@example.test")
        forbidden = await client.post(
            f"/api/v1/teams/{team_id}/members",
            headers={"X-CSRF-Token": str(analyst["csrfToken"])},
            json={"userId": _user_id(app, "rfa.team@example.test")},
        )
        assert forbidden.status_code == 403

        # Another team's manager cannot even see this team.
        cm_manager = await login(client, "collection.manager@example.test")
        invisible = await client.post(
            f"/api/v1/teams/{team_id}/members",
            headers={"X-CSRF-Token": str(cm_manager["csrfToken"])},
            json={"userId": new_member},
        )
        assert invisible.status_code == 404

        manager = await login(client, "rfa.manager@example.test")
        removed = await client.delete(
            f"/api/v1/teams/{team_id}/members/{new_member}",
            headers={"X-CSRF-Token": str(manager["csrfToken"])},
        )
        assert removed.status_code == 200
        assert all(m["userId"] != new_member for m in removed.json()["members"])

        await login(client, "admin@example.test")
        audit = await client.get("/api/v1/audit")
        events = [event["eventType"] for event in audit.json()["events"]]
        assert "team_member_added" in events
        assert "team_member_removed" in events


@pytest.mark.asyncio
async def test_calendar_entries_respect_member_and_manager_boundaries() -> None:
    app = _app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        analyst = await login(client, "analyst@example.test")
        team_id = await _team_id(client, "RFA Assessment Team")
        own = await client.post(
            f"/api/v1/teams/{team_id}/calendar",
            headers={"X-CSRF-Token": str(analyst["csrfToken"])},
            json={
                "userId": _user_id(app, "analyst@example.test"),
                "date": "2026-07-20",
                "status": "leave",
                "note": "Annual leave.",
            },
        )
        assert own.status_code == 200
        # A member cannot write another member's entry.
        for_other = await client.post(
            f"/api/v1/teams/{team_id}/calendar",
            headers={"X-CSRF-Token": str(analyst["csrfToken"])},
            json={
                "userId": _user_id(app, "analyst.geo@example.test"),
                "date": "2026-07-20",
                "status": "leave",
            },
        )
        assert for_other.status_code == 403

        manager = await login(client, "rfa.manager@example.test")
        for_member = await client.post(
            f"/api/v1/teams/{team_id}/calendar",
            headers={"X-CSRF-Token": str(manager["csrfToken"])},
            json={
                "userId": _user_id(app, "analyst.geo@example.test"),
                "date": "2026-07-21",
                "status": "on_task",
                "note": "Standing task.",
            },
        )
        assert for_member.status_code == 200

        window = await client.get(f"/api/v1/teams/{team_id}/calendar?from=2026-07-20&to=2026-07-22")
        assert window.status_code == 200
        assert len(window.json()["entries"]) == 2
        bad_window = await client.get(
            f"/api/v1/teams/{team_id}/calendar?from=2026-07-22&to=2026-07-20"
        )
        assert bad_window.status_code == 422

        entry_id = for_member.json()["id"]
        analyst = await login(client, "analyst@example.test")
        not_yours = await client.delete(
            f"/api/v1/teams/{team_id}/calendar/{entry_id}",
            headers={"X-CSRF-Token": str(analyst["csrfToken"])},
        )
        assert not_yours.status_code == 403
        manager = await login(client, "rfa.manager@example.test")
        deleted = await client.delete(
            f"/api/v1/teams/{team_id}/calendar/{entry_id}",
            headers={"X-CSRF-Token": str(manager["csrfToken"])},
        )
        assert deleted.status_code == 204
        missing = await client.delete(
            f"/api/v1/teams/{team_id}/calendar/{uuid4()}",
            headers={"X-CSRF-Token": str(manager["csrfToken"])},
        )
        assert missing.status_code == 404


@pytest.mark.asyncio
async def test_availability_combines_calendar_and_live_assignments() -> None:
    app = _app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        # A live in-flight assignment for analyst@example.test.
        ticket_id = await analyst_assignment_ticket(client)
        manager = await login(client, "rfa.manager@example.test")
        assigned = await client.post(
            f"/api/v1/analyst/tasks/{ticket_id}/assign",
            headers={"X-CSRF-Token": str(manager["csrfToken"])},
            json={"analystUserIds": [_user_id(app, "analyst@example.test")]},
        )
        assert assigned.status_code == 200
        team_id = await _team_id(client, "RFA Assessment Team")
        leave = await client.post(
            f"/api/v1/teams/{team_id}/calendar",
            headers={"X-CSRF-Token": str(manager["csrfToken"])},
            json={
                "userId": _user_id(app, "analyst.maritime@example.test"),
                "date": "2026-07-15",
                "status": "leave",
            },
        )
        assert leave.status_code == 200

        availability = await client.get(f"/api/v1/teams/{team_id}/availability?date=2026-07-15")

    assert availability.status_code == 200
    body = availability.json()
    # Manager + rfa.team + four analysts are on the seed team.
    assert body["members"] == 6
    assert body["onLeave"] == 1
    assert body["assignedLive"] == 1
    assert body["free"] == 4


@pytest.mark.asyncio
async def test_profiles_are_self_edited_and_visible_to_teammates_only() -> None:
    app = _app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        analyst = await login(client, "analyst@example.test")
        updated = await client.put(
            "/api/v1/users/me/profile",
            headers={"X-CSRF-Token": str(analyst["csrfToken"])},
            json={
                "title": "Senior Imagery Analyst",
                "specialisms": ["IMINT", "Maritime", "IMINT"],
                "bio": "MOCK DATA ONLY analyst profile.",
            },
        )
        assert updated.status_code == 200
        assert updated.json()["title"] == "Senior Imagery Analyst"
        assert updated.json()["specialisms"] == ["IMINT", "Maritime"]

        analyst_id = _user_id(app, "analyst@example.test")
        await login(client, "rfa.manager@example.test")
        teammate_view = await client.get(f"/api/v1/users/{analyst_id}/profile")
        assert teammate_view.status_code == 200
        assert teammate_view.json()["title"] == "Senior Imagery Analyst"

        await login(client, "user@example.test")
        outsider_view = await client.get(f"/api/v1/users/{analyst_id}/profile")
        assert outsider_view.status_code == 404
        own_default = await client.get("/api/v1/users/me/profile")
        assert own_default.status_code == 200


def test_team_records_round_trip_through_the_codec() -> None:
    team = OrgTeam(
        team_id=uuid4(),
        name="Codec Team",
        kind=TeamKind.RFA,
        manager_user_ids=(uuid4(),),
        member_user_ids=(uuid4(), uuid4()),
        capability_team_id="RFA-MARITIME",
    )
    entry = TeamCalendarEntry(
        entry_id=uuid4(),
        team_id=team.team_id,
        user_id=team.member_user_ids[0],
        entry_date="2026-07-15",
        status=CalendarStatus.LEAVE,
        note="Round trip.",
    )
    profile = UserProfile(user_id=uuid4(), title="Analyst", specialisms=("IMINT",), bio="Bio.")

    for record in (team, entry, profile):
        decoded: Any = decode_value(encode_value(record))
        assert decoded == record
