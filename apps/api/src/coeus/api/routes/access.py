from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from coeus.api.dependencies import (
    get_access_services,
    get_csrf_validated_session,
    get_current_session,
    require_permission,
)
from coeus.core.permissions import Permission
from coeus.domain.access import AccessControlGroup
from coeus.domain.auth import AuthenticatedSession
from coeus.schemas.access import (
    AccessCheckResponse,
    AccessControlGroupListResponse,
    AccessControlGroupResponse,
    AccessDiagnosticsRequest,
    AccessDiagnosticsResponse,
    AddAccessControlGroupMemberRequest,
    CreateAccessControlGroupRequest,
    UpdateAccessControlGroupRequest,
)
from coeus.services.access import AccessServices

router = APIRouter(tags=["access-control"])


@router.get("/acgs", response_model=AccessControlGroupListResponse)
async def list_acgs(
    authenticated: Annotated[AuthenticatedSession, Depends(get_current_session)],
    access_services: Annotated[AccessServices, Depends(get_access_services)],
) -> AccessControlGroupListResponse:
    acgs = access_services.acgs.list_visible_acgs(authenticated.user)
    return AccessControlGroupListResponse(
        acgs=[_to_acg_response(access_services, acg) for acg in acgs]
    )


@router.post("/acgs", response_model=AccessControlGroupResponse, status_code=201)
async def create_acg(
    payload: CreateAccessControlGroupRequest,
    authenticated: Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)],
    access_services: Annotated[AccessServices, Depends(get_access_services)],
) -> AccessControlGroupResponse:
    acg = access_services.acgs.create_acg(
        authenticated.user,
        payload.code,
        payload.name,
        payload.description,
        payload.owner_user_id,
    )
    return _to_acg_response(access_services, acg)


@router.get("/acgs/{acg_id}", response_model=AccessControlGroupResponse)
async def get_acg(
    acg_id: UUID,
    authenticated: Annotated[AuthenticatedSession, Depends(get_current_session)],
    access_services: Annotated[AccessServices, Depends(get_access_services)],
) -> AccessControlGroupResponse:
    acg = access_services.acgs.get_visible_acg(authenticated.user, acg_id)
    return _to_acg_response(access_services, acg)


@router.patch("/acgs/{acg_id}", response_model=AccessControlGroupResponse)
async def update_acg(
    acg_id: UUID,
    payload: UpdateAccessControlGroupRequest,
    authenticated: Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)],
    access_services: Annotated[AccessServices, Depends(get_access_services)],
) -> AccessControlGroupResponse:
    acg = access_services.acgs.update_acg(
        authenticated.user,
        acg_id,
        name=payload.name,
        description=payload.description,
        is_active=payload.is_active,
    )
    return _to_acg_response(access_services, acg)


@router.post("/acgs/{acg_id}/members", response_model=AccessControlGroupResponse)
async def add_acg_member(
    acg_id: UUID,
    payload: AddAccessControlGroupMemberRequest,
    authenticated: Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)],
    access_services: Annotated[AccessServices, Depends(get_access_services)],
) -> AccessControlGroupResponse:
    access_services.acgs.add_user(authenticated.user, acg_id, payload.user_id)
    acg = access_services.acgs.get_visible_acg(authenticated.user, acg_id)
    return _to_acg_response(access_services, acg)


@router.delete("/acgs/{acg_id}/members/{user_id}", status_code=204)
async def remove_acg_member(
    acg_id: UUID,
    user_id: UUID,
    authenticated: Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)],
    access_services: Annotated[AccessServices, Depends(get_access_services)],
) -> None:
    access_services.acgs.remove_user(authenticated.user, acg_id, user_id)


@router.post(
    "/store/products/{product_id}/access-diagnostics",
    response_model=AccessDiagnosticsResponse,
)
async def diagnose_product_access(
    product_id: UUID,
    payload: AccessDiagnosticsRequest,
    _authenticated: Annotated[
        AuthenticatedSession,
        Depends(require_permission(Permission.SYSTEM_CONFIGURE)),
    ],
    _csrf_validated: Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)],
    access_services: Annotated[AccessServices, Depends(get_access_services)],
) -> AccessDiagnosticsResponse:
    decision = access_services.diagnostics.diagnose_product(product_id, payload.user_id)
    return AccessDiagnosticsResponse(
        allowed=decision.allowed,
        reason=decision.reason,
        checks=[
            AccessCheckResponse(name=check.name, passed=check.passed, reason=check.reason)
            for check in decision.checks
        ],
    )


def _to_acg_response(
    access_services: AccessServices, acg: AccessControlGroup
) -> AccessControlGroupResponse:
    return AccessControlGroupResponse(
        acg_id=acg.acg_id,
        code=acg.code,
        name=acg.name,
        description=acg.description,
        owner_user_id=acg.owner_user_id,
        is_active=acg.is_active,
        member_user_ids=list(access_services.acgs.list_member_ids(acg.acg_id)),
    )
