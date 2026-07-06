from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response

from coeus.api.dependencies import (
    get_auth_service,
    get_csrf_validated_session,
    get_current_session,
    get_registration_service,
    get_settings,
)
from coeus.core.config import Settings
from coeus.domain.auth import AuthenticatedSession, UserAccount
from coeus.domain.rbac import default_route_for_roles
from coeus.schemas.auth import AuthSessionResponse, LoginRequest, UserProfileResponse
from coeus.schemas.registration import RegistrationSubmitRequest, RegistrationSubmitResponse
from coeus.services.auth import AuthService
from coeus.services.registration import RegistrationService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=AuthSessionResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    settings: Annotated[Settings, Depends(get_settings)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> AuthSessionResponse:
    existing_session_id = request.cookies.get(settings.session_cookie_name)
    result = auth_service.login(
        payload.username,
        payload.password,
        replace_session_id=existing_session_id,
    )
    _set_session_cookie(response, settings, result.session.session_id)
    return AuthSessionResponse(
        user=_to_user_response(result.user, result.default_route),
        csrf_token=result.session.csrf_token,
    )


@router.post("/register", response_model=RegistrationSubmitResponse, status_code=202)
async def register(
    payload: RegistrationSubmitRequest,
    registration_service: Annotated[RegistrationService, Depends(get_registration_service)],
) -> RegistrationSubmitResponse:
    registration_service.submit(
        payload.username,
        payload.display_name,
        payload.justification,
        payload.password,
    )
    return RegistrationSubmitResponse(status="pending")


@router.post("/logout", status_code=204)
async def logout(
    response: Response,
    settings: Annotated[Settings, Depends(get_settings)],
    authenticated: Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> None:
    auth_service.logout(authenticated.session.session_id)
    _clear_session_cookie(response, settings)


@router.get("/me", response_model=AuthSessionResponse)
async def me(
    authenticated: Annotated[AuthenticatedSession, Depends(get_current_session)],
) -> AuthSessionResponse:
    return AuthSessionResponse(
        user=_to_user_response(
            authenticated.user,
            default_route_for_roles(authenticated.user.roles),
        ),
        csrf_token=authenticated.session.csrf_token,
    )


@router.post("/session/rotate", response_model=AuthSessionResponse)
async def rotate_session(
    response: Response,
    settings: Annotated[Settings, Depends(get_settings)],
    authenticated: Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> AuthSessionResponse:
    rotated = auth_service.rotate_session(authenticated.session.session_id)
    _set_session_cookie(response, settings, rotated.session_id)
    return AuthSessionResponse(
        user=_to_user_response(
            authenticated.user,
            default_route_for_roles(authenticated.user.roles),
        ),
        csrf_token=rotated.csrf_token,
    )


def _set_session_cookie(response: Response, settings: Settings, session_id: str) -> None:
    response.set_cookie(
        key=settings.session_cookie_name,
        value=session_id,
        max_age=settings.session_ttl_seconds,
        httponly=True,
        secure=settings.secure_cookies,
        samesite="strict",
    )


def _clear_session_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        key=settings.session_cookie_name,
        httponly=True,
        secure=settings.secure_cookies,
        samesite="strict",
    )


def _to_user_response(user: UserAccount, default_route: str) -> UserProfileResponse:
    return UserProfileResponse(
        user_id=user.user_id,
        username=user.username,
        display_name=user.display_name,
        roles=[role.value for role in sorted(user.roles)],
        permissions=[permission.value for permission in sorted(user.permissions)],
        default_route=default_route,
    )
