from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from coeus.api.dependencies import (
    get_csrf_validated_session,
    get_current_session,
    get_team_availability_service,
    get_team_calendar_service,
    get_team_repository,
    get_team_workspace_service,
)
from coeus.api.presenters.teams import (
    availability_response,
    calendar_entry_response,
    profile_response,
    team_response,
)
from coeus.domain.auth import AuthenticatedSession
from coeus.domain.teams import CalendarStatus
from coeus.repositories.teams import TeamRepository
from coeus.schemas.teams import (
    AvailabilityResponse,
    CalendarEntryRequest,
    CalendarEntryResponse,
    CalendarResponse,
    ProfileResponse,
    ProfileUpdateRequest,
    TeamListResponse,
    TeamMemberCandidateListResponse,
    TeamMemberRequest,
    TeamResponse,
)
from coeus.services.team_availability import TeamAvailabilityService, TeamCalendarService
from coeus.services.team_workspace import TeamWorkspaceService

router = APIRouter(prefix="/teams", tags=["teams"])
profile_router = APIRouter(prefix="/users", tags=["teams"])

WorkspaceDep = Annotated[TeamWorkspaceService, Depends(get_team_workspace_service)]
AvailabilityDep = Annotated[TeamAvailabilityService, Depends(get_team_availability_service)]
CalendarDep = Annotated[TeamCalendarService, Depends(get_team_calendar_service)]
RepositoryDep = Annotated[TeamRepository, Depends(get_team_repository)]
SessionDep = Annotated[AuthenticatedSession, Depends(get_current_session)]
CsrfSessionDep = Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)]


@router.get("", response_model=TeamListResponse)
async def list_teams(
    authenticated: SessionDep, workspace: WorkspaceDep, teams: RepositoryDep
) -> TeamListResponse:
    return TeamListResponse(
        teams=[
            team_response(team, workspace.roster(authenticated.user, team.team_id), teams)
            for team in workspace.list_teams(authenticated.user)
        ]
    )


@router.post("/{team_id}/members", response_model=TeamResponse)
async def add_team_member(
    team_id: UUID,
    payload: TeamMemberRequest,
    authenticated: CsrfSessionDep,
    workspace: WorkspaceDep,
    teams: RepositoryDep,
) -> TeamResponse:
    team = workspace.add_member(authenticated.user, team_id, payload.user_id)
    return team_response(team, workspace.roster(authenticated.user, team_id), teams)


@router.get("/{team_id}/member-candidates", response_model=TeamMemberCandidateListResponse)
async def team_member_candidates(
    team_id: UUID,
    authenticated: SessionDep,
    workspace: WorkspaceDep,
    teams: RepositoryDep,
    query: Annotated[str, Query(min_length=3, max_length=120)],
) -> TeamMemberCandidateListResponse:
    candidates = workspace.member_candidates(authenticated.user, team_id, query)
    # Candidate profile details are returned only through this manager-authorised boundary.
    placeholder_team = workspace.team_details(authenticated.user, team_id)
    return TeamMemberCandidateListResponse(
        users=[
            team_response(placeholder_team, (candidate,), teams).members[0]
            for candidate in candidates
        ]
    )


@router.delete("/{team_id}/members/{user_id}", response_model=TeamResponse)
async def remove_team_member(
    team_id: UUID,
    user_id: UUID,
    authenticated: CsrfSessionDep,
    workspace: WorkspaceDep,
    teams: RepositoryDep,
) -> TeamResponse:
    team = workspace.remove_member(authenticated.user, team_id, user_id)
    return team_response(team, workspace.roster(authenticated.user, team_id), teams)


@router.get("/{team_id}/calendar", response_model=CalendarResponse)
async def team_calendar(
    team_id: UUID,
    authenticated: SessionDep,
    workspace: WorkspaceDep,
    availability: AvailabilityDep,
    date_from: Annotated[str, Query(alias="from", pattern=r"^\d{4}-\d{2}-\d{2}$")],
    date_to: Annotated[str, Query(alias="to", pattern=r"^\d{4}-\d{2}-\d{2}$")],
) -> CalendarResponse:
    team = workspace.team_details(authenticated.user, team_id)
    entries = availability.calendar(team, date_from, date_to)
    return CalendarResponse(entries=[calendar_entry_response(entry) for entry in entries])


@router.post("/{team_id}/calendar", response_model=CalendarEntryResponse)
async def add_calendar_entry(
    team_id: UUID,
    payload: CalendarEntryRequest,
    authenticated: CsrfSessionDep,
    workspace: WorkspaceDep,
    calendar: CalendarDep,
) -> CalendarEntryResponse:
    team = workspace.team_details(authenticated.user, team_id)
    entry = calendar.add_entry(
        authenticated.user,
        team,
        payload.user_id,
        payload.entry_date,
        CalendarStatus(payload.status),
        payload.note,
    )
    return calendar_entry_response(entry)


@router.delete("/{team_id}/calendar/{entry_id}", status_code=204)
async def remove_calendar_entry(
    team_id: UUID,
    entry_id: UUID,
    authenticated: CsrfSessionDep,
    workspace: WorkspaceDep,
    calendar: CalendarDep,
) -> None:
    team = workspace.team_details(authenticated.user, team_id)
    calendar.remove_entry(authenticated.user, team, entry_id)


@router.get("/{team_id}/availability", response_model=AvailabilityResponse)
async def team_availability(
    team_id: UUID,
    authenticated: SessionDep,
    workspace: WorkspaceDep,
    availability: AvailabilityDep,
    date: Annotated[str, Query(pattern=r"^\d{4}-\d{2}-\d{2}$")],
) -> AvailabilityResponse:
    team = workspace.team_details(authenticated.user, team_id)
    return availability_response(availability.availability(team, date))


@profile_router.get("/me/profile", response_model=ProfileResponse)
async def my_profile(authenticated: SessionDep, workspace: WorkspaceDep) -> ProfileResponse:
    return profile_response(workspace.get_profile(authenticated.user, authenticated.user.user_id))


@profile_router.put("/me/profile", response_model=ProfileResponse)
async def update_my_profile(
    payload: ProfileUpdateRequest,
    authenticated: CsrfSessionDep,
    workspace: WorkspaceDep,
) -> ProfileResponse:
    return profile_response(
        workspace.update_my_profile(
            authenticated.user,
            payload.title,
            tuple(payload.specialisms),
            payload.bio,
        )
    )


@profile_router.get("/{user_id}/profile", response_model=ProfileResponse)
async def user_profile(
    user_id: UUID, authenticated: SessionDep, workspace: WorkspaceDep
) -> ProfileResponse:
    return profile_response(workspace.get_profile(authenticated.user, user_id))
