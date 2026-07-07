from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from coeus.api.dependencies import (
    get_csrf_validated_session,
    get_user_admin_service,
    require_permission,
)
from coeus.core.errors import AppError
from coeus.core.permissions import Permission
from coeus.domain.auth import AuthenticatedSession, RoleName, UserAccount
from coeus.schemas.users_admin import (
    AdminUserListResponse,
    AdminUserResponse,
    CredentialResetResponse,
    UserClearanceRequest,
    UserRolesRequest,
    UserStatusRequest,
)
from coeus.services.user_admin import UserAdminService

router = APIRouter(prefix="/admin/users", tags=["admin"])


@router.get("", response_model=AdminUserListResponse)
async def list_users(
    authenticated: Annotated[
        AuthenticatedSession,
        Depends(require_permission(Permission.USER_ASSIGN_ROLE)),
    ],
    service: Annotated[UserAdminService, Depends(get_user_admin_service)],
) -> AdminUserListResponse:
    return AdminUserListResponse(
        users=[_to_user_response(user) for user in service.list_users(authenticated.user)]
    )


@router.put("/{user_id}/roles", response_model=AdminUserResponse)
async def set_roles(
    user_id: UUID,
    payload: UserRolesRequest,
    authenticated: Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)],
    service: Annotated[UserAdminService, Depends(get_user_admin_service)],
) -> AdminUserResponse:
    roles = frozenset(_to_role(role) for role in payload.roles)
    return _to_user_response(service.set_roles(authenticated.user, user_id, roles))


@router.put("/{user_id}/clearance", response_model=AdminUserResponse)
async def set_clearance(
    user_id: UUID,
    payload: UserClearanceRequest,
    authenticated: Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)],
    service: Annotated[UserAdminService, Depends(get_user_admin_service)],
) -> AdminUserResponse:
    return _to_user_response(
        service.set_clearance(authenticated.user, user_id, payload.clearance_level)
    )


@router.put("/{user_id}/status", response_model=AdminUserResponse)
async def set_status(
    user_id: UUID,
    payload: UserStatusRequest,
    authenticated: Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)],
    service: Annotated[UserAdminService, Depends(get_user_admin_service)],
) -> AdminUserResponse:
    return _to_user_response(service.set_active(authenticated.user, user_id, payload.is_active))


@router.post("/{user_id}/credential-reset", response_model=CredentialResetResponse)
async def reset_credential(
    user_id: UUID,
    authenticated: Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)],
    service: Annotated[UserAdminService, Depends(get_user_admin_service)],
) -> CredentialResetResponse:
    return CredentialResetResponse(
        temporary_credential=service.reset_credential(authenticated.user, user_id)
    )


def _to_role(value: str) -> RoleName:
    try:
        return RoleName(value)
    except ValueError as error:
        raise AppError(422, "role_unknown", "One or more roles are not recognised.") from error


def _to_user_response(user: UserAccount) -> AdminUserResponse:
    return AdminUserResponse(
        user_id=user.user_id,
        username=user.username,
        display_name=user.display_name,
        roles=sorted(role.value for role in user.roles),
        clearance_level=user.clearance_level,
        is_active=user.is_active,
    )
