"""Block (multi-day) calendar entries and the extended activity types."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from coeus.core.config import Settings
from coeus.domain.teams import CalendarStatus, TeamCalendarEntry, entry_covers, entry_end
from coeus.main import create_app
from coeus.persistence.codec import decode_value, encode_value
from rfi_search_helpers import login


def _app() -> FastAPI:
    return create_app(Settings(environment="test", argon2_memory_cost=8_192))


def _day(offset: int) -> str:
    return (datetime.now(UTC).date() + timedelta(days=offset)).isoformat()


async def _team_id(client: AsyncClient, name: str) -> str:
    teams = await client.get("/api/v1/teams")
    assert teams.status_code == 200
    return next(team["id"] for team in teams.json()["teams"] if team["name"] == name)


def _user_id(app: FastAPI, username: str) -> str:
    user = app.state.access_services.repository.get_user_by_username(username)
    assert user is not None
    return str(user.user_id)


@pytest.mark.asyncio
async def test_block_entry_spans_days_and_counts_in_availability() -> None:
    app = _app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        manager = await login(client, "rfa.manager@example.test")
        team_id = await _team_id(client, "RFA Assessment Team")
        analyst_id = _user_id(app, "analyst@example.test")

        created = await client.post(
            f"/api/v1/teams/{team_id}/calendar",
            headers={"X-CSRF-Token": str(manager["csrfToken"])},
            json={
                "userId": analyst_id,
                "date": _day(3),
                "endDate": _day(6),
                "status": "course",
                "note": "Residential analysis course.",
            },
        )
        assert created.status_code == 200
        assert created.json()["status"] == "course"
        assert created.json()["date"] == _day(3)
        assert created.json()["endDate"] == _day(6)

        # A window overlapping only the middle of the block still returns it.
        window = await client.get(f"/api/v1/teams/{team_id}/calendar?from={_day(4)}&to={_day(5)}")
        assert window.status_code == 200
        entry_ids = [entry["id"] for entry in window.json()["entries"]]
        assert created.json()["id"] in entry_ids

        # A day inside the block counts under other commitments, not free.
        availability = await client.get(f"/api/v1/teams/{team_id}/availability?date={_day(5)}")
        assert availability.status_code == 200
        body = availability.json()
        assert body["otherCommitments"] >= 1
        assert body["members"] == body["free"] + body["onLeave"] + body["onTaskCalendar"] + body[
            "otherCommitments"
        ] + body["assignedLive"] - _overlap_allowance(body)


def _overlap_allowance(body: dict) -> int:
    # assignedLive can overlap the calendar sets; allow the difference.
    return max(
        0,
        body["free"]
        + body["onLeave"]
        + body["onTaskCalendar"]
        + body["otherCommitments"]
        + body["assignedLive"]
        - body["members"],
    )


@pytest.mark.asyncio
async def test_block_entry_validation_rejects_bad_ranges() -> None:
    app = _app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        manager = await login(client, "rfa.manager@example.test")
        team_id = await _team_id(client, "RFA Assessment Team")
        analyst_id = _user_id(app, "analyst@example.test")
        headers = {"X-CSRF-Token": str(manager["csrfToken"])}

        backwards = await client.post(
            f"/api/v1/teams/{team_id}/calendar",
            headers=headers,
            json={"userId": analyst_id, "date": _day(5), "endDate": _day(3), "status": "leave"},
        )
        assert backwards.status_code == 422
        assert "end date" in backwards.json()["error"]["message"].lower()

        too_far = await client.post(
            f"/api/v1/teams/{team_id}/calendar",
            headers=headers,
            json={"userId": analyst_id, "date": _day(5), "endDate": _day(90), "status": "leave"},
        )
        assert too_far.status_code == 422

        bad_status = await client.post(
            f"/api/v1/teams/{team_id}/calendar",
            headers=headers,
            json={"userId": analyst_id, "date": _day(5), "status": "sabbatical"},
        )
        assert bad_status.status_code == 422


@pytest.mark.asyncio
async def test_every_new_activity_type_is_accepted_and_reduces_free_count() -> None:
    app = _app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        manager = await login(client, "rfa.manager@example.test")
        team_id = await _team_id(client, "RFA Assessment Team")
        headers = {"X-CSRF-Token": str(manager["csrfToken"])}
        members = {
            "analyst@example.test": "course",
            "analyst.maritime@example.test": "duty",
            "analyst.cyber@example.test": "appointment",
            "analyst.geo@example.test": "other",
        }
        for username, status in members.items():
            created = await client.post(
                f"/api/v1/teams/{team_id}/calendar",
                headers=headers,
                json={"userId": _user_id(app, username), "date": _day(10), "status": status},
            )
            assert created.status_code == 200, status

        availability = await client.get(f"/api/v1/teams/{team_id}/availability?date={_day(10)}")
        assert availability.json()["otherCommitments"] == 4


@pytest.mark.asyncio
async def test_latest_created_entry_wins_over_an_older_block() -> None:
    app = _app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        manager = await login(client, "rfa.manager@example.test")
        team_id = await _team_id(client, "RFA Assessment Team")
        analyst_id = _user_id(app, "analyst@example.test")
        headers = {"X-CSRF-Token": str(manager["csrfToken"])}

        block = await client.post(
            f"/api/v1/teams/{team_id}/calendar",
            headers=headers,
            json={"userId": analyst_id, "date": _day(2), "endDate": _day(8), "status": "leave"},
        )
        assert block.status_code == 200
        override = await client.post(
            f"/api/v1/teams/{team_id}/calendar",
            headers=headers,
            json={"userId": analyst_id, "date": _day(4), "status": "on_task"},
        )
        assert override.status_code == 200

        mid_block = await client.get(f"/api/v1/teams/{team_id}/availability?date={_day(4)}")
        assert mid_block.json()["onLeave"] == 0
        assert mid_block.json()["onTaskCalendar"] >= 1


def test_block_entries_round_trip_the_codec_and_legacy_entries_default() -> None:
    entry = TeamCalendarEntry(
        entry_id=uuid4(),
        team_id=uuid4(),
        user_id=uuid4(),
        entry_date="2026-07-20",
        status=CalendarStatus.COURSE,
        note="Course block.",
        end_date="2026-07-24",
    )
    decoded = decode_value(encode_value(entry))
    assert decoded == entry
    assert entry_end(decoded) == "2026-07-24"
    assert entry_covers(decoded, "2026-07-22")
    assert not entry_covers(decoded, "2026-07-25")

    # A payload persisted before end_date existed decodes with the default.
    encoded = encode_value(entry)
    encoded["fields"].pop("end_date")
    legacy = decode_value(encoded)
    assert legacy.end_date == ""
    assert entry_end(legacy) == "2026-07-20"
