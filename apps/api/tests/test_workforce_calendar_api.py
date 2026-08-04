"""HTTP contract tests for canonical personal calendars."""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from coeus.api.organisation_dependencies import get_workforce_calendar
from coeus.core.config import Settings
from coeus.domain.workforce_calendar import (
    AvailabilityEffect,
    CalendarActivity,
    CalendarAggregateCell,
    CalendarCommitment,
    CalendarEvent,
    CalendarEventSource,
    CalendarMutationDenied,
    CalendarMutationPreview,
    CalendarMutationResult,
    CalendarMutationSnapshot,
    CalendarPrivacy,
    CalendarProjection,
    CalendarProjectionDenied,
    CalendarProjectionDetail,
    CalendarProjectionEntry,
    CalendarProjectionScope,
    CalendarTiming,
    CommitmentResponseState,
)
from coeus.main import create_app
from rfi_search_helpers import login


class _Calendar:
    def __init__(self) -> None:
        self.command = None
        self.event = None
        self.denied = False
        self.projection_denied = False
        self.projection_args = None
        self.commitment = None

    def personal_calendar(self, actor_id, window_start, window_end):  # type: ignore[no-untyped-def]
        del actor_id, window_start, window_end
        return () if self.event is None else (self.event,)

    def preview(self, request, actor_id):  # type: ignore[no-untyped-def]
        del actor_id
        if self.denied:
            raise CalendarMutationDenied("Synthetic calendar scope denied.")
        self.event = request.event
        return CalendarMutationPreview(
            request,
            CalendarMutationSnapshot(0, 1, "b" * 64),
            "a" * 64,
        )

    def execute(self, command):  # type: ignore[no-untyped-def]
        self.command = command
        self.event = command.request.event
        return CalendarMutationResult(command.request.event.event_id, 1)

    def team_projection(
        self,
        actor_id,
        unit_id,
        window_start,
        window_end,
        *,
        include_descendants=False,
        request_detail=False,
    ):  # type: ignore[no-untyped-def]
        if self.projection_denied:
            raise CalendarProjectionDenied("Synthetic hidden calendar.")
        self.projection_args = (
            actor_id,
            unit_id,
            window_start,
            window_end,
            include_descendants,
            request_detail,
        )
        return CalendarProjection(
            root_unit_id=unit_id,
            scope=(
                CalendarProjectionScope.DESCENDANTS
                if include_descendants
                else CalendarProjectionScope.DIRECT
            ),
            generated_at=window_start,
            unit_ids=(unit_id,),
            member_count=None,
            suppressed=include_descendants,
            truncated=False,
            entries=()
            if include_descendants
            else (
                CalendarProjectionEntry(
                    unit_id,
                    CalendarTiming(
                        "Europe/London",
                        starts_at=window_start,
                        ends_at=window_start + timedelta(hours=1),
                    ),
                    AvailabilityEffect.UNAVAILABLE,
                    CalendarProjectionDetail.AVAILABILITY,
                ),
            ),
            aggregates=(CalendarAggregateCell(unit_id, window_start.date(), None, None, True),)
            if include_descendants
            else (),
        )

    def commitments(self, actor_id):  # type: ignore[no-untyped-def]
        del actor_id
        return () if self.commitment is None else (self.commitment,)

    def respond_to_commitment(self, actor_id, response):  # type: ignore[no-untyped-def]
        assert actor_id == response.subject_user_id
        self.commitment = CalendarCommitment(
            self.commitment.event,
            response.state,
            response.expected_version + 1,
            self.commitment.notified_at,
            datetime.now(UTC),
        )
        return self.commitment


def _app():  # type: ignore[no-untyped-def]
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    calendar = _Calendar()
    app.dependency_overrides[get_workforce_calendar] = lambda: calendar
    return app, calendar


def _payload(actor_id: UUID) -> dict[str, object]:
    start = datetime.now(UTC) + timedelta(days=1)
    return {
        "operation": "create",
        "event": {
            "eventId": str(uuid4()),
            "ownerUserId": str(actor_id),
            "source": "personal",
            "activity": "training",
            "timing": {
                "timeZone": "Europe/London",
                "startsAt": start.isoformat(),
                "endsAt": (start + timedelta(hours=2)).isoformat(),
            },
            "availability": "partial",
            "privacy": "team_summary",
            "createdByUserId": str(actor_id),
            "note": "Synthetic professional development.",
            "version": 1,
        },
        "expectedVersion": 0,
        "authorisingGrantId": None,
        "reason": "Add my synthetic training event.",
    }


@pytest.mark.asyncio
async def test_personal_calendar_preview_execute_and_read_contract() -> None:
    app, calendar = _app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        session = await login(client, "admin@example.test")
        actor = app.state.access_services.repository.get_user_by_username("admin@example.test")
        assert actor is not None
        payload = _payload(actor.user_id)
        headers = {"X-CSRF-Token": session["csrfToken"]}
        preview = await client.post("/api/v1/calendar/previews", headers=headers, json=payload)
        assert preview.status_code == 200
        assert preview.json()["snapshot"] == {
            "currentVersion": 0,
            "overlappingEvents": 1,
            "stateDigest": "b" * 64,
        }
        result = await client.post(
            "/api/v1/calendar/commands",
            headers=headers,
            json={
                "commandId": str(uuid4()),
                "idempotencyKey": "add-personal-training",
                "request": payload,
                "previewHash": preview.json()["previewHash"],
            },
        )
        assert result.status_code == 200 and result.json()["version"] == 1
        start = datetime.now(UTC)
        response = await client.get(
            "/api/v1/calendar/me",
            params={
                "windowStart": start.isoformat(),
                "windowEnd": (start + timedelta(days=7)).isoformat(),
            },
        )
    assert response.status_code == 200
    assert response.json()["events"][0]["activity"] == "training"
    assert response.json()["events"][0]["timing"]["startsAt"] is not None
    assert "starts_at" not in response.json()["events"][0]["timing"]
    assert calendar.command.actor_user_id == actor.user_id


@pytest.mark.asyncio
async def test_subject_lists_acknowledges_and_disputes_manager_commitment() -> None:
    app, calendar = _app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        session = await login(client, "admin@example.test")
        actor = app.state.access_services.repository.get_user_by_username("admin@example.test")
        assert actor is not None
        now = datetime.now(UTC)
        calendar.commitment = CalendarCommitment(
            CalendarEvent(
                uuid4(),
                actor.user_id,
                CalendarEventSource.MANAGER,
                CalendarActivity.MEETING,
                CalendarTiming(
                    "Europe/London",
                    starts_at=now + timedelta(days=1),
                    ends_at=now + timedelta(days=1, hours=1),
                ),
                AvailabilityEffect.PARTIAL,
                CalendarPrivacy.TEAM_SUMMARY,
                uuid4(),
                "Synthetic manager commitment",
                manager_scope_unit_id=uuid4(),
            ),
            CommitmentResponseState.PENDING,
            1,
            now,
        )
        listed = await client.get("/api/v1/calendar/commitments/me")
        assert listed.status_code == 200
        assert listed.json()["commitments"][0]["responseState"] == "pending"
        event_id = calendar.commitment.event.event_id
        acknowledged = await client.post(
            f"/api/v1/calendar/commitments/{event_id}/responses",
            headers={"X-CSRF-Token": session["csrfToken"]},
            json={"state": "acknowledged", "expectedVersion": 1},
        )
        assert acknowledged.status_code == 200
        assert acknowledged.json()["responseState"] == "acknowledged"
        disputed = await client.post(
            f"/api/v1/calendar/commitments/{event_id}/responses",
            headers={"X-CSRF-Token": session["csrfToken"]},
            json={
                "state": "disputed",
                "expectedVersion": 2,
                "reason": "The synthetic timing conflicts with approved leave.",
            },
        )
    assert disputed.status_code == 200
    assert disputed.json()["responseVersion"] == 3


@pytest.mark.asyncio
async def test_calendar_denial_is_bounded() -> None:
    app, calendar = _app()
    calendar.denied = True
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        session = await login(client, "admin@example.test")
        actor = app.state.access_services.repository.get_user_by_username("admin@example.test")
        assert actor is not None
        response = await client.post(
            "/api/v1/calendar/previews",
            headers={"X-CSRF-Token": session["csrfToken"]},
            json=_payload(actor.user_id),
        )
    assert response.status_code == 403
    assert response.json()["error"] == {
        "code": "calendar_change_denied",
        "message": "You do not have authority for this calendar change.",
    }


@pytest.mark.asyncio
async def test_descendant_calendar_projection_contract_is_redacted() -> None:
    app, calendar = _app()
    unit_id = uuid4()
    start = datetime.now(UTC)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        await login(client, "admin@example.test")
        response = await client.get(
            f"/api/v1/calendar/units/{unit_id}",
            params={
                "windowStart": start.isoformat(),
                "windowEnd": (start + timedelta(days=7)).isoformat(),
                "includeDescendants": "true",
                "view": "availability",
            },
        )
    assert response.status_code == 200
    body = response.json()
    assert body["scope"] == "descendants" and body["suppressed"] is True
    assert body["memberCount"] is None and body["truncated"] is False
    assert body["entries"] == []
    assert body["aggregates"] == [
        {
            "unitId": str(unit_id),
            "day": start.date().isoformat(),
            "memberCount": None,
            "unavailableCount": None,
            "suppressed": True,
        }
    ]
    assert calendar.projection_args[-2:] == (True, False)


@pytest.mark.asyncio
async def test_calendar_projection_denial_uses_generic_not_found_posture() -> None:
    app, calendar = _app()
    calendar.projection_denied = True
    unit_id = uuid4()
    start = datetime.now(UTC)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        await login(client, "admin@example.test")
        response = await client.get(
            f"/api/v1/calendar/units/{unit_id}",
            params={
                "windowStart": start.isoformat(),
                "windowEnd": (start + timedelta(days=7)).isoformat(),
                "view": "detail",
            },
        )
    assert response.status_code == 404
    assert response.json()["error"] == {
        "code": "calendar_not_found",
        "message": "Calendar not found.",
    }
