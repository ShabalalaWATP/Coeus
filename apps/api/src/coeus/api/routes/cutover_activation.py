"""Admin-only exact-candidate cutover ceremony."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request

from coeus.api.cutover_activation_contracts import call_cutover, manifest, release_state
from coeus.api.dependencies import get_auth_service, get_settings
from coeus.api.organisation_dependencies import (
    get_cutover_activation,
    get_organisation_admin_csrf_session,
    get_organisation_admin_session,
)
from coeus.api.routes.auth import client_ip
from coeus.core.config import Settings
from coeus.domain.auth import AuthenticatedSession
from coeus.domain.cutover_activation import CutoverSlice
from coeus.schemas.cutover_activation import (
    CutoverApprovalRequest,
    CutoverExecutionRequest,
    CutoverExecutionResponse,
    CutoverManifestPayload,
    CutoverReleaseStateResponse,
    CutoverSliceApprovalResponse,
    CutoverSlicePreviewResponse,
)
from coeus.services.auth import AuthService
from coeus.services.cutover_activation import CutoverActivationService

router = APIRouter(
    prefix="/admin/organisation/cutover-release", tags=["organisation administration"]
)
AdminSession = Annotated[AuthenticatedSession, Depends(get_organisation_admin_session)]
AdminCsrfSession = Annotated[AuthenticatedSession, Depends(get_organisation_admin_csrf_session)]
Activation = Annotated[CutoverActivationService, Depends(get_cutover_activation)]


@router.get("", response_model=CutoverReleaseStateResponse)
def get_cutover_release(_: AdminSession, service: Activation) -> CutoverReleaseStateResponse:
    return release_state(call_cutover(service.state))


@router.post("/previews/{slice}", response_model=CutoverSlicePreviewResponse)
def preview_cutover_slice(
    slice: CutoverSlice,
    payload: CutoverManifestPayload,
    authenticated: AdminCsrfSession,
    service: Activation,
) -> CutoverSlicePreviewResponse:
    preview = call_cutover(lambda: service.preview(slice, manifest(payload), authenticated.user))
    return CutoverSlicePreviewResponse(**vars(preview))


@router.post("/approvals", response_model=CutoverSliceApprovalResponse)
def approve_cutover_slice(
    payload: CutoverApprovalRequest,
    request: Request,
    authenticated: AdminCsrfSession,
    service: Activation,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> CutoverSliceApprovalResponse:
    auth_service.reauthenticate(
        authenticated,
        payload.current_password.get_secret_value(),
        client_ip=client_ip(request, settings),
    )
    approval = call_cutover(
        lambda: service.approve(
            payload.slice,
            payload.candidate_hash,
            payload.preview_hash,
            payload.approval_role,
            authenticated.user,
            reauthenticated=True,
        )
    )
    return CutoverSliceApprovalResponse(**vars(approval))


@router.post("/execute/{slice}", response_model=CutoverExecutionResponse)
def execute_cutover_slice(
    slice: CutoverSlice,
    payload: CutoverExecutionRequest,
    request: Request,
    authenticated: AdminCsrfSession,
    service: Activation,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> CutoverExecutionResponse:
    auth_service.reauthenticate(
        authenticated,
        payload.current_password.get_secret_value(),
        client_ip=client_ip(request, settings),
    )
    result = call_cutover(
        lambda: service.execute(
            slice,
            payload.candidate_hash,
            payload.approval_ids,
            authenticated.user,
            reauthenticated=True,
        )
    )
    return CutoverExecutionResponse(**vars(result))
