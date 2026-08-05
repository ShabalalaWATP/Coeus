"""Authenticated home and explicitly managed organisation workspaces."""

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from coeus.api.dependencies import get_current_session
from coeus.api.organisation_dependencies import get_organisation_workspace, get_team_task_board
from coeus.core.errors import AppError
from coeus.domain.auth import AuthenticatedSession
from coeus.domain.organisation_workspace import OrganisationWorkspaceIntegrityError
from coeus.domain.team_task_board import (
    TeamBoardColumn,
    TeamBoardQuery,
    TeamBoardScope,
    TeamTaskBoardDenied,
    TeamTaskBoardIntegrityError,
    TeamTaskCard,
)
from coeus.schemas.organisation_workspace import (
    OrganisationWorkspaceListResponse,
    OrganisationWorkspaceResponse,
    OrganisationWorkspaceUnitResponse,
)
from coeus.schemas.team_task_board import (
    TeamBoardAggregateResponse,
    TeamTaskBoardResponse,
    TeamTaskCardResponse,
    TeamTaskPackageResponse,
)
from coeus.services.organisation_workspace import OrganisationWorkspaceService
from coeus.services.team_task_board import TeamTaskBoardService

router = APIRouter(prefix="/organisation/workspaces", tags=["organisation workspaces"])
SessionDep = Annotated[AuthenticatedSession, Depends(get_current_session)]
WorkspaceDep = Annotated[OrganisationWorkspaceService, Depends(get_organisation_workspace)]
BoardDep = Annotated[TeamTaskBoardService, Depends(get_team_task_board)]


@router.get("", response_model=OrganisationWorkspaceListResponse)
async def list_workspaces(
    authenticated: SessionDep,
    service: WorkspaceDep,
) -> OrganisationWorkspaceListResponse:
    try:
        page = service.list_for_actor(authenticated.user.user_id)
    except OrganisationWorkspaceIntegrityError as error:
        raise AppError(
            503,
            "organisation_workspace_unavailable",
            "Your organisation workspace is temporarily unavailable.",
        ) from error
    return OrganisationWorkspaceListResponse(
        workspaces=[
            OrganisationWorkspaceResponse(
                unit=OrganisationWorkspaceUnitResponse(
                    id=workspace.unit.unit_id,
                    name=workspace.unit.name,
                    shortName=workspace.unit.short_name,
                    category=workspace.unit.category,
                    timeZone=workspace.unit.time_zone,
                ),
                relationship=workspace.relationship,
                managed=workspace.managed,
                includeDescendants=workspace.include_descendants,
                canViewAvailability=workspace.can_view_availability,
                canViewDetail=workspace.can_view_detail,
                canViewTasks=workspace.can_view_tasks,
                planningGrantId=workspace.planning_grant_id,
                configurationGrantId=workspace.configuration_grant_id,
                configurationGrantVersion=workspace.configuration_grant_version,
                calendarManagementGrantId=workspace.calendar_management_grant_id,
                canViewPeople=workspace.can_view_people,
                canViewCapabilities=workspace.can_view_capabilities,
                canConfigure=workspace.can_configure,
                exportGrantId=workspace.export_grant_id,
                exportGrantVersion=workspace.export_grant_version,
            )
            for workspace in page.workspaces
        ],
        as_of=page.as_of,
        truncated=page.truncated,
    )


@router.get(
    "/{unit_id}/board",
    response_model=TeamTaskBoardResponse,
    response_model_exclude_none=True,
)
async def get_team_board(
    unit_id: UUID,
    authenticated: SessionDep,
    service: BoardDep,
    include_completed: Annotated[bool, Query(alias="includeCompleted")] = False,
    scope: TeamBoardScope = TeamBoardScope.DIRECT,
    columns: Annotated[list[TeamBoardColumn] | None, Query(alias="column")] = None,
    unit_ids: Annotated[list[UUID] | None, Query(alias="unitId")] = None,
    priority: Annotated[str | None, Query(max_length=40)] = None,
    due_from: Annotated[date | None, Query(alias="dueFrom")] = None,
    due_to: Annotated[date | None, Query(alias="dueTo")] = None,
    completed_after: Annotated[date | None, Query(alias="completedAfter")] = None,
    cursor: Annotated[str | None, Query(max_length=512)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> TeamTaskBoardResponse:
    try:
        board = service.get_board(
            authenticated.user.user_id,
            unit_id,
            TeamBoardQuery(
                scope=scope,
                include_completed=include_completed,
                columns=tuple(columns or ()),
                unit_ids=tuple(unit_ids or ()),
                priority=priority,
                due_from=due_from,
                due_to=due_to,
                completed_after=completed_after,
                cursor=cursor,
                limit=limit,
            ),
        )
    except ValueError as error:
        raise AppError(422, "invalid_team_board_query", "The board query is invalid.") from error
    except TeamTaskBoardDenied as error:
        raise AppError(404, "team_workspace_not_found", "Team workspace was not found.") from error
    except TeamTaskBoardIntegrityError as error:
        raise AppError(
            503, "team_board_unavailable", "The team board is temporarily unavailable."
        ) from error
    return TeamTaskBoardResponse(
        unitId=board.unit_id,
        cards=[_card_response(card) for card in board.cards],
        asOf=board.as_of,
        truncated=board.truncated,
        nextCursor=board.next_cursor,
        aggregates=[TeamBoardAggregateResponse(**vars(item)) for item in board.aggregates],
        scope=board.scope,
    )


def _card_response(card: TeamTaskCard) -> TeamTaskCardResponse:
    values = vars(card)
    return TeamTaskCardResponse(
        **{
            **values,
            "packages": [TeamTaskPackageResponse(**vars(package)) for package in card.packages],
        }
    )
