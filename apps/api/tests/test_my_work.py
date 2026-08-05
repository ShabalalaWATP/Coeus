"""Canonical personal work contracts and defensive cursor behaviour."""

from datetime import UTC, date, datetime
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from coeus.api.organisation_dependencies import get_my_work
from coeus.core.config import Settings
from coeus.domain.my_work import (
    MyWorkCard,
    MyWorkColumn,
    MyWorkCursor,
    MyWorkIntegrityError,
    MyWorkPage,
    decode_cursor,
    encode_cursor,
)
from coeus.domain.team_task_ownership import WorkflowLeg
from coeus.main import create_app
from coeus.services.my_work import MyWorkService
from rfi_search_helpers import login


class _Store:
    def __init__(self, result: MyWorkPage | Exception) -> None:
        self.result = result
        self.call: tuple[UUID, bool, MyWorkColumn | None, str | None, int] | None = None

    def list_my_work(
        self,
        actor_id: UUID,
        *,
        include_completed: bool,
        column: MyWorkColumn | None,
        cursor: str | None,
        limit: int,
    ) -> MyWorkPage:
        self.call = (actor_id, include_completed, column, cursor, limit)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def test_cursor_round_trip_and_invalid_values() -> None:
    cursor = MyWorkCursor(
        datetime(2026, 8, 3, 12, tzinfo=UTC), uuid4(), WorkflowLeg.RFA, 2, uuid4()
    )
    assert decode_cursor(encode_cursor(cursor)) == cursor
    for invalid in ("", "%%%", "e30", "WyIyMDI2LTA4LTAzVDEyOjAwOjAwIl0"):
        with pytest.raises(ValueError, match="cursor is invalid"):
            decode_cursor(invalid)


def test_service_enforces_page_bound() -> None:
    page = MyWorkPage((), datetime(2026, 8, 3, tzinfo=UTC), None)
    service = MyWorkService(_Store(page))
    with pytest.raises(ValueError, match="between one and 100"):
        service.list_my_work(uuid4(), limit=101)


@pytest.mark.asyncio
async def test_http_projection_is_actor_only_and_privacy_minimised() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    ticket_id, package_id = uuid4(), uuid4()
    page = MyWorkPage(
        (
            MyWorkCard(
                ticket_id,
                WorkflowLeg.RFA,
                package_id,
                "TCK-001",
                "Synthetic request",
                "Assess source reporting",
                MyWorkColumn.IN_PROGRESS,
                2,
                date(2026, 8, 10),
                datetime(2026, 8, 9, 12, tzinfo=UTC),
                None,
                None,
                3,
                2,
                4,
            ),
        ),
        datetime(2026, 8, 3, 12, tzinfo=UTC),
        "next-page",
    )
    store = _Store(page)
    app.dependency_overrides[get_my_work] = lambda: MyWorkService(store)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        assert (await client.get("/api/v1/organisation/workspaces/my-work")).status_code == 401
        await login(client, "analyst@example.test")
        response = await client.get(
            "/api/v1/organisation/workspaces/my-work"
            "?includeCompleted=true&column=in_progress&cursor=cursor&limit=5"
        )
    assert response.status_code == 200
    body = response.json()
    assert body["cards"][0] == {
        "ticketId": str(ticket_id),
        "workflowLeg": "rfa",
        "packageId": str(package_id),
        "reference": "TCK-001",
        "ticketTitle": "Synthetic request",
        "packageTitle": "Assess source reporting",
        "column": "in_progress",
        "priority": 2,
        "targetDate": "2026-08-10",
        "dueAt": "2026-08-09T12:00:00Z",
        "blockedCode": None,
        "reviewAt": None,
        "ticketVersion": 3,
        "ownershipVersion": 2,
        "packageVersion": 4,
    }
    assert "requester" not in str(body).lower()
    actor = app.state.access_services.repository.get_user_by_username("analyst@example.test")
    assert actor is not None
    assert store.call == (actor.user_id, True, MyWorkColumn.IN_PROGRESS, "cursor", 5)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("result", "status", "code"),
    (
        (ValueError("bad cursor"), 422, "invalid_my_work_query"),
        (MyWorkIntegrityError("bad row"), 503, "my_work_unavailable"),
    ),
)
async def test_http_projection_returns_bounded_failures(
    result: Exception, status: int, code: str
) -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    app.dependency_overrides[get_my_work] = lambda: MyWorkService(_Store(result))
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        await login(client, "analyst@example.test")
        response = await client.get("/api/v1/organisation/workspaces/my-work")
    assert response.status_code == status
    assert response.json()["error"]["code"] == code
