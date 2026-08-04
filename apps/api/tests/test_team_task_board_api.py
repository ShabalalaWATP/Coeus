"""HTTP contracts for the privacy-minimised team task board."""

from datetime import UTC, date, datetime
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from coeus.api.organisation_dependencies import get_team_task_board
from coeus.core.config import Settings
from coeus.domain.team_task_board import (
    TeamBoardAggregate,
    TeamBoardColumn,
    TeamBoardQuery,
    TeamTaskBoard,
    TeamTaskBoardDenied,
    TeamTaskBoardIntegrityError,
    TeamTaskCard,
    TeamTaskPackage,
)
from coeus.domain.team_task_ownership import WorkflowLeg
from coeus.main import create_app
from rfi_search_helpers import login


class _BoardService:
    def __init__(self, result: TeamTaskBoard | Exception) -> None:
        self.result = result
        self.call: tuple[UUID, UUID, TeamBoardQuery] | None = None

    def get_board(
        self,
        actor_id: UUID,
        unit_id: UUID,
        query: TeamBoardQuery,
    ) -> TeamTaskBoard:
        self.call = (actor_id, unit_id, query)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


@pytest.mark.asyncio
async def test_board_is_actor_scoped_bounded_and_minimal() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    unit_id, ticket_id, package_id, owner_id = uuid4(), uuid4(), uuid4(), uuid4()
    service = _BoardService(
        TeamTaskBoard(
            unit_id,
            (
                TeamTaskCard(
                    ticket_id,
                    WorkflowLeg.RFA,
                    "TCK-001",
                    "Synthetic task",
                    TeamBoardColumn.IN_PROGRESS,
                    "High",
                    date(2026, 8, 21),
                    datetime(2026, 8, 3, 11, tzinfo=UTC),
                    4,
                    2,
                    (
                        TeamTaskPackage(
                            package_id,
                            "Review reporting",
                            "in_progress",
                            owner_id,
                            90,
                            45,
                            datetime(2026, 8, 20, 16, tzinfo=UTC),
                            2,
                            3,
                        ),
                    ),
                ),
            ),
            datetime(2026, 8, 3, 12, tzinfo=UTC),
            False,
        )
    )
    app.dependency_overrides[get_team_task_board] = lambda: service
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        unauthenticated = await client.get(f"/api/v1/organisation/workspaces/{unit_id}/board")
        assert unauthenticated.status_code == 401
        await login(client, "user@example.test")
        response = await client.get(
            f"/api/v1/organisation/workspaces/{unit_id}/board?includeCompleted=true&limit=25"
        )
    assert response.status_code == 200
    payload = response.json()
    assert payload["cards"] == [
        {
            "ticketId": str(ticket_id),
            "workflowLeg": "rfa",
            "reference": "TCK-001",
            "title": "Synthetic task",
            "column": "in_progress",
            "priority": "High",
            "targetDate": "2026-08-21",
            "ticketUpdatedAt": "2026-08-03T11:00:00Z",
            "ticketVersion": 4,
            "ownershipVersion": 2,
            "packages": [
                {
                    "packageId": str(package_id),
                    "title": "Review reporting",
                    "state": "in_progress",
                    "accountableUserId": str(owner_id),
                    "estimatedMinutes": 90,
                    "remainingMinutes": 45,
                    "dueAt": "2026-08-20T16:00:00Z",
                    "priority": 2,
                    "version": 3,
                }
            ],
        }
    ]
    actor = app.state.access_services.repository.get_user_by_username("user@example.test")
    assert actor is not None and service.call is not None
    assert service.call[:2] == (actor.user_id, unit_id)
    assert service.call[2].include_completed and service.call[2].limit == 25


@pytest.mark.asyncio
async def test_management_board_returns_only_allowlisted_aggregate_counts() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    unit_id, child_id = uuid4(), uuid4()
    service = _BoardService(
        TeamTaskBoard(
            unit_id,
            (),
            datetime(2026, 8, 3, 12, tzinfo=UTC),
            False,
            None,
            (
                TeamBoardAggregate(
                    child_id, "Restricted child", TeamBoardColumn.BLOCKED, None, True
                ),
            ),
        )
    )
    app.dependency_overrides[get_team_task_board] = lambda: service
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        await login(client, "user@example.test")
        response = await client.get(
            f"/api/v1/organisation/workspaces/{unit_id}/board"
            "?scope=descendants&column=blocked&dueFrom=2026-08-01&limit=10"
        )
    assert response.status_code == 200
    assert response.json()["aggregates"] == [
        {
            "unitId": str(child_id),
            "unitName": "Restricted child",
            "column": "blocked",
            "suppressed": True,
        }
    ]
    assert "reference" not in str(response.json()["aggregates"]).lower()
    assert service.call is not None
    query = service.call[2]
    assert query.scope.value == "descendants"
    assert query.columns == (TeamBoardColumn.BLOCKED,)


@pytest.mark.asyncio
async def test_management_board_rejects_invalid_date_and_priority_filters() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    service = _BoardService(TeamTaskBoard(uuid4(), (), datetime.now(UTC), False))
    app.dependency_overrides[get_team_task_board] = lambda: service
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        await login(client, "user@example.test")
        bad_dates = await client.get(
            f"/api/v1/organisation/workspaces/{uuid4()}/board?dueFrom=2026-08-02&dueTo=2026-08-01"
        )
        bad_priority = await client.get(
            f"/api/v1/organisation/workspaces/{uuid4()}/board?priority="
        )
    assert bad_dates.status_code == 422
    assert bad_dates.json()["error"]["code"] == "invalid_team_board_query"
    assert bad_priority.status_code == 422


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error", "status", "code"),
    (
        (TeamTaskBoardDenied(), 404, "team_workspace_not_found"),
        (TeamTaskBoardIntegrityError(), 503, "team_board_unavailable"),
    ),
)
async def test_board_failures_do_not_disclose_scope_or_ticket_details(
    error: Exception, status: int, code: str
) -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    app.dependency_overrides[get_team_task_board] = lambda: _BoardService(error)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        await login(client, "user@example.test")
        response = await client.get(f"/api/v1/organisation/workspaces/{uuid4()}/board")
    assert response.status_code == status
    assert response.json()["error"]["code"] == code
