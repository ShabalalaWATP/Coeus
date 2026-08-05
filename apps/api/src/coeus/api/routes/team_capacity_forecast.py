"""Advisory direct-team capacity forecast under exact assignment authority."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from coeus.api.dependencies import get_current_session
from coeus.api.organisation_dependencies import get_team_capacity_forecast
from coeus.core.errors import AppError
from coeus.domain.auth import AuthenticatedSession
from coeus.domain.team_capacity_forecast import (
    TeamCapacityForecastDenied,
    TeamCapacityForecastIntegrityError,
)
from coeus.schemas.team_capacity_forecast import TeamCapacityForecastResponse
from coeus.services.team_capacity_forecast import TeamCapacityForecastService

router = APIRouter(prefix="/organisation/workspaces", tags=["team capacity"])


@router.get("/{unit_id}/capacity", response_model=TeamCapacityForecastResponse)
async def get_team_capacity_forecast_route(
    unit_id: UUID,
    authenticated: Annotated[AuthenticatedSession, Depends(get_current_session)],
    service: Annotated[TeamCapacityForecastService, Depends(get_team_capacity_forecast)],
    authorising_grant_id: Annotated[UUID, Query(alias="authorisingGrantId")],
    window_start: Annotated[datetime, Query(alias="windowStart")],
    window_end: Annotated[datetime, Query(alias="windowEnd")],
) -> TeamCapacityForecastResponse:
    try:
        forecast = service.forecast(
            authenticated.user.user_id,
            unit_id,
            authorising_grant_id,
            window_start,
            window_end,
        )
    except TeamCapacityForecastDenied as error:
        raise AppError(404, "team_workspace_not_found", "Team workspace was not found.") from error
    except ValueError as error:
        raise AppError(422, "invalid_capacity_window", "The capacity window is invalid.") from error
    except TeamCapacityForecastIntegrityError as error:
        raise AppError(
            503, "capacity_forecast_unavailable", "Team capacity is temporarily unavailable."
        ) from error
    return TeamCapacityForecastResponse(**vars(forecast))
