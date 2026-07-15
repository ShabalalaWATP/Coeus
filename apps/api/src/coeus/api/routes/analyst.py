from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from coeus.api.dependencies import (
    get_analyst_assignment_service,
    get_analyst_workflow_service,
    get_csrf_validated_session,
    get_current_session,
    get_team_availability_service,
)
from coeus.api.presenters.analyst import candidate_response, conversation_response, task_response
from coeus.api.presenters.teams import availability_response
from coeus.domain.auth import AuthenticatedSession
from coeus.domain.tickets import (
    RoutingRoute,
    WorkPackageStatus,
)
from coeus.schemas.analyst import (
    AnalystAssignmentRequest,
    AnalystCandidateListResponse,
    AnalystConversationResponse,
    AnalystNoteRequest,
    AnalystTaskListResponse,
    AnalystTaskResponse,
    AssignmentTeamListResponse,
    AssignmentTeamResponse,
    DraftAssetRequest,
    DraftProductRequest,
    LinkProductRequest,
    WorkPackageUpdateRequest,
)
from coeus.schemas.teams import AvailabilityResponse
from coeus.services.analyst_assignment_service import AnalystAssignmentService
from coeus.services.analyst_drafts import DraftAssetInput, DraftProductInput
from coeus.services.analyst_workflow import AnalystWorkflowService
from coeus.services.team_availability import TeamAvailabilityService

router = APIRouter(prefix="/analyst", tags=["analyst"])


@router.get("/candidates", response_model=AnalystCandidateListResponse)
async def analyst_candidates(
    authenticated: Annotated[AuthenticatedSession, Depends(get_current_session)],
    assignments: Annotated[AnalystAssignmentService, Depends(get_analyst_assignment_service)],
    route: RoutingRoute,
    team_id: Annotated[UUID, Query(alias="teamId")],
) -> AnalystCandidateListResponse:
    return AnalystCandidateListResponse(
        analysts=[
            candidate_response(user)
            for user in assignments.analyst_candidates(authenticated.user, route, team_id)
        ]
    )


@router.get("/assignment-teams", response_model=AssignmentTeamListResponse)
async def assignment_teams(
    authenticated: Annotated[AuthenticatedSession, Depends(get_current_session)],
    assignments: Annotated[AnalystAssignmentService, Depends(get_analyst_assignment_service)],
    route: RoutingRoute,
) -> AssignmentTeamListResponse:
    return AssignmentTeamListResponse(
        teams=[
            AssignmentTeamResponse(team_id=team.team_id, name=team.name, kind=team.kind.value)
            for team in assignments.assignment_teams(authenticated.user, route)
        ]
    )


@router.get(
    "/assignment-teams/{team_id}/availability",
    response_model=AvailabilityResponse,
)
async def assignment_team_availability(
    team_id: UUID,
    authenticated: Annotated[AuthenticatedSession, Depends(get_current_session)],
    assignments: Annotated[AnalystAssignmentService, Depends(get_analyst_assignment_service)],
    availability: Annotated[TeamAvailabilityService, Depends(get_team_availability_service)],
    route: RoutingRoute,
    entry_date: Annotated[str, Query(alias="date", pattern=r"^\d{4}-\d{2}-\d{2}$")],
) -> AvailabilityResponse:
    team = assignments.assignment_team(authenticated.user, route, team_id)
    return availability_response(availability.availability(team, entry_date))


@router.get("/tasks", response_model=AnalystTaskListResponse)
async def analyst_tasks(
    authenticated: Annotated[AuthenticatedSession, Depends(get_current_session)],
    analyst: Annotated[AnalystWorkflowService, Depends(get_analyst_workflow_service)],
) -> AnalystTaskListResponse:
    return AnalystTaskListResponse(
        tasks=[
            task_response(ticket, authenticated.user, analyst)
            for ticket in analyst.list_tasks(authenticated.user)
        ]
    )


@router.get("/tasks/{ticket_id}", response_model=AnalystTaskResponse)
async def analyst_task_details(
    ticket_id: UUID,
    authenticated: Annotated[AuthenticatedSession, Depends(get_current_session)],
    analyst: Annotated[AnalystWorkflowService, Depends(get_analyst_workflow_service)],
) -> AnalystTaskResponse:
    return task_response(
        analyst.task_details(authenticated.user, ticket_id), authenticated.user, analyst
    )


@router.get("/tasks/{ticket_id}/conversation", response_model=AnalystConversationResponse)
async def analyst_task_conversation(
    ticket_id: UUID,
    authenticated: Annotated[AuthenticatedSession, Depends(get_current_session)],
    analyst: Annotated[AnalystWorkflowService, Depends(get_analyst_workflow_service)],
) -> AnalystConversationResponse:
    ticket = analyst.task_details(authenticated.user, ticket_id)
    return AnalystConversationResponse(messages=conversation_response(ticket))


@router.post("/tasks/{ticket_id}/assign", response_model=AnalystTaskResponse)
async def assign_analysts(
    ticket_id: UUID,
    payload: AnalystAssignmentRequest,
    authenticated: Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)],
    assignments: Annotated[AnalystAssignmentService, Depends(get_analyst_assignment_service)],
    analyst: Annotated[AnalystWorkflowService, Depends(get_analyst_workflow_service)],
) -> AnalystTaskResponse:
    return task_response(
        assignments.assign(
            authenticated.user,
            ticket_id,
            tuple(payload.analyst_user_ids),
            tuple(payload.work_packages),
            payload.team_id,
        ),
        authenticated.user,
        analyst,
    )


@router.post("/tasks/{ticket_id}/notes", response_model=AnalystTaskResponse)
async def add_note(
    ticket_id: UUID,
    payload: AnalystNoteRequest,
    authenticated: Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)],
    analyst: Annotated[AnalystWorkflowService, Depends(get_analyst_workflow_service)],
) -> AnalystTaskResponse:
    return task_response(
        analyst.add_note(authenticated.user, ticket_id, payload.body),
        authenticated.user,
        analyst,
    )


@router.post("/tasks/{ticket_id}/products", response_model=AnalystTaskResponse)
async def link_product(
    ticket_id: UUID,
    payload: LinkProductRequest,
    authenticated: Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)],
    analyst: Annotated[AnalystWorkflowService, Depends(get_analyst_workflow_service)],
) -> AnalystTaskResponse:
    return task_response(
        analyst.link_product(authenticated.user, ticket_id, payload.product_id),
        authenticated.user,
        analyst,
    )


@router.patch("/tasks/{ticket_id}/work-packages/{package_id}", response_model=AnalystTaskResponse)
async def update_work_package(
    ticket_id: UUID,
    package_id: UUID,
    payload: WorkPackageUpdateRequest,
    authenticated: Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)],
    analyst: Annotated[AnalystWorkflowService, Depends(get_analyst_workflow_service)],
) -> AnalystTaskResponse:
    return task_response(
        analyst.update_work_package(
            authenticated.user,
            ticket_id,
            package_id,
            WorkPackageStatus(payload.status),
        ),
        authenticated.user,
        analyst,
    )


@router.post("/tasks/{ticket_id}/drafts", response_model=AnalystTaskResponse)
async def save_draft(
    ticket_id: UUID,
    payload: DraftProductRequest,
    authenticated: Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)],
    analyst: Annotated[AnalystWorkflowService, Depends(get_analyst_workflow_service)],
) -> AnalystTaskResponse:
    return task_response(
        analyst.create_draft(authenticated.user, ticket_id, _draft_input(payload)),
        authenticated.user,
        analyst,
    )


@router.post("/tasks/{ticket_id}/submit", response_model=AnalystTaskResponse)
async def submit_work(
    ticket_id: UUID,
    authenticated: Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)],
    analyst: Annotated[AnalystWorkflowService, Depends(get_analyst_workflow_service)],
) -> AnalystTaskResponse:
    return task_response(
        analyst.submit_work(authenticated.user, ticket_id), authenticated.user, analyst
    )


def _draft_input(payload: DraftProductRequest) -> DraftProductInput:
    return DraftProductInput(
        title=payload.title,
        summary=payload.summary,
        product_type=payload.product_type,
        content=payload.content,
        assets=tuple(_asset_input(asset) for asset in payload.assets),
    )


def _asset_input(asset: DraftAssetRequest) -> DraftAssetInput:
    return DraftAssetInput(
        name=asset.name,
        asset_type=asset.asset_type,
        mime_type=asset.mime_type,
        size_bytes=asset.size_bytes,
        sha256=asset.sha256,
    )
