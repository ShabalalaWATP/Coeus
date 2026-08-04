"""Integrated, actor-authorised team workspace operations."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response

from coeus.api.dependencies import get_csrf_validated_session, get_current_session
from coeus.api.organisation_dependencies import get_workspace_operations
from coeus.core.errors import AppError
from coeus.domain.auth import AuthenticatedSession
from coeus.domain.workspace_operations import (
    WorkspaceCommand,
    WorkspaceExport,
    WorkspaceOperationsConflict,
    WorkspaceOperationsDenied,
    WorkspaceScope,
)
from coeus.schemas.workspace_operations import (
    AnalyticsResponse,
    CapabilitiesResponse,
    CapabilityResponse,
    CreateExportRequest,
    ExportResponse,
    MetricResponse,
    OverviewResponse,
    PeopleResponse,
    PersonResponse,
    PolicyResponse,
    SavePolicyRequest,
    SearchResponse,
    SearchResultResponse,
)
from coeus.services.workspace_operations import WorkspaceOperationsService

router = APIRouter(prefix="/organisation/workspaces", tags=["workspace operations"])
Session = Annotated[AuthenticatedSession, Depends(get_current_session)]
CsrfSession = Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)]
Service = Annotated[WorkspaceOperationsService, Depends(get_workspace_operations)]


@router.get("/{unit_id}/overview", response_model=OverviewResponse)
async def get_overview(
    unit_id: UUID,
    authenticated: Session,
    service: Service,
    scope: WorkspaceScope = WorkspaceScope.DIRECT,
) -> OverviewResponse:
    try:
        item = service.overview(authenticated.user.user_id, unit_id, scope)
        # vars(item) already carries the domain metrics, so they are replaced
        # rather than passed a second time.
        fields = {key: value for key, value in vars(item).items() if key != "metrics"}
        return OverviewResponse(
            **fields, metrics=[MetricResponse(**vars(metric)) for metric in item.metrics]
        )
    except WorkspaceOperationsDenied as error:
        raise _not_found() from error


@router.get("/{unit_id}/people", response_model=PeopleResponse)
async def get_people(
    unit_id: UUID,
    authenticated: Session,
    service: Service,
    scope: WorkspaceScope = WorkspaceScope.DIRECT,
    query: Annotated[str | None, Query(min_length=2, max_length=120)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> PeopleResponse:
    try:
        items = service.people(authenticated.user.user_id, unit_id, scope, query, limit + 1)
        return PeopleResponse(
            items=[PersonResponse(**vars(item)) for item in items[:limit]],
            truncated=len(items) > limit,
        )
    except WorkspaceOperationsDenied as error:
        raise _not_found() from error


@router.get("/{unit_id}/capabilities", response_model=CapabilitiesResponse)
async def get_capabilities(
    unit_id: UUID,
    authenticated: Session,
    service: Service,
    scope: WorkspaceScope = WorkspaceScope.DIRECT,
) -> CapabilitiesResponse:
    try:
        items = service.capabilities(authenticated.user.user_id, unit_id, scope)
        return CapabilitiesResponse(items=[CapabilityResponse(**vars(item)) for item in items])
    except WorkspaceOperationsDenied as error:
        raise _not_found() from error


@router.get("/{unit_id}/policy", response_model=PolicyResponse)
async def get_policy(unit_id: UUID, authenticated: Session, service: Service) -> PolicyResponse:
    try:
        return PolicyResponse(**vars(service.policy(authenticated.user.user_id, unit_id)))
    except WorkspaceOperationsDenied as error:
        raise _not_found() from error


@router.put("/{unit_id}/policy", response_model=PolicyResponse)
async def save_policy(
    unit_id: UUID, payload: SavePolicyRequest, authenticated: CsrfSession, service: Service
) -> PolicyResponse:
    command = WorkspaceCommand(
        payload.command_id,
        payload.idempotency_key,
        authenticated.user.user_id,
        "save_workspace_policy",
        {
            "unit_id": unit_id,
            "authorising_grant_id": payload.authorising_grant_id,
            "expected_grant_version": payload.expected_grant_version,
            "expected_version": payload.expected_version,
            "expected_delivery_policy_version": payload.expected_delivery_policy_version,
            "wip_limit": payload.wip_limit,
            "service_target_hours": payload.service_target_hours,
            "planning_cadence": payload.planning_cadence,
            "planning_weekday": payload.planning_weekday,
            "planning_local_time": payload.planning_local_time,
            "planning_duration_minutes": payload.planning_duration_minutes,
        },
    )
    try:
        return PolicyResponse(**vars(service.save_policy(command)))
    except WorkspaceOperationsDenied as error:
        raise _not_found() from error
    except WorkspaceOperationsConflict as error:
        raise AppError(409, "workspace_policy_conflict", str(error)) from error


@router.get("/{unit_id}/search", response_model=SearchResponse)
async def search_workspace(
    unit_id: UUID,
    authenticated: Session,
    service: Service,
    query: Annotated[str, Query(min_length=2, max_length=120)],
    scope: WorkspaceScope = WorkspaceScope.DIRECT,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    store_only: bool = False,
    cursor: Annotated[int, Query(ge=0, le=500)] = 0,
) -> SearchResponse:
    try:
        items = service.search(
            authenticated.user,
            unit_id,
            scope,
            query.strip(),
            limit + 1,
            store_only=store_only,
            offset=cursor,
        )
        return SearchResponse(
            items=[SearchResultResponse(**vars(item)) for item in items[:limit]],
            truncated=len(items) > limit,
            next_cursor=cursor + limit if len(items) > limit else None,
        )
    except WorkspaceOperationsDenied as error:
        raise _not_found() from error


@router.get("/{unit_id}/analytics", response_model=AnalyticsResponse)
async def get_analytics(
    unit_id: UUID,
    authenticated: Session,
    service: Service,
    scope: WorkspaceScope = WorkspaceScope.DIRECT,
) -> AnalyticsResponse:
    try:
        item = service.analytics(authenticated.user.user_id, unit_id, scope)
        return AnalyticsResponse(
            **vars(item), metrics=[MetricResponse(**vars(metric)) for metric in item.metrics]
        )
    except WorkspaceOperationsDenied as error:
        raise _not_found() from error


@router.post("/{unit_id}/exports", response_model=ExportResponse, status_code=201)
async def create_export(
    unit_id: UUID, payload: CreateExportRequest, authenticated: CsrfSession, service: Service
) -> ExportResponse:
    command = WorkspaceCommand(
        payload.command_id,
        payload.idempotency_key,
        authenticated.user.user_id,
        "create_workspace_export",
        {
            "unit_id": unit_id,
            "export_id": payload.export_id,
            "include_descendants": payload.include_descendants,
            "authorising_grant_id": payload.authorising_grant_id,
            "expected_grant_version": payload.expected_grant_version,
            "format": payload.format,
        },
    )
    try:
        return _export_response(service.create_export(command))
    except WorkspaceOperationsDenied as error:
        raise _not_found() from error
    except WorkspaceOperationsConflict as error:
        raise AppError(409, "workspace_export_conflict", str(error)) from error


@router.get("/exports/{export_id}", response_model=ExportResponse)
async def get_export(export_id: UUID, authenticated: Session, service: Service) -> ExportResponse:
    try:
        return _export_response(service.get_export(authenticated.user.user_id, export_id))
    except WorkspaceOperationsDenied as error:
        raise _not_found() from error


@router.get("/exports/{export_id}/download")
async def download_export(export_id: UUID, authenticated: Session, service: Service) -> Response:
    try:
        content = service.export_csv(authenticated.user.user_id, export_id)
    except WorkspaceOperationsDenied as error:
        raise _not_found() from error
    return Response(
        content,
        media_type="text/csv; charset=utf-8",
        headers={
            "Cache-Control": "no-store",
            "Content-Disposition": f'attachment; filename="istari-team-export-{export_id}.csv"',
            "X-Content-Type-Options": "nosniff",
        },
    )


def _export_response(item: WorkspaceExport) -> ExportResponse:
    return ExportResponse(**vars(item))


def _not_found() -> AppError:
    return AppError(404, "team_workspace_not_found", "Team workspace was not found.")
