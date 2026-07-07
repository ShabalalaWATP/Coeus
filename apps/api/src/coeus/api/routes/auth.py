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
from coeus.schemas.auth import (
    AuthSessionResponse,
    LoginRequest,
    PasswordChangeRequest,
    UserProfileResponse,
)
from coeus.schemas.registration import RegistrationSubmitRequest, RegistrationSubmitResponse
from coeus.services.auth import AuthService
from coeus.services.registration import RegistrationService

router = APIRouter(prefix="/auth", tags=["auth"])


def client_ip(request: Request, settings: Settings) -> str | None:
    """Return the client address used for authentication throttling.

    X-Forwarded-For is only honoured when COEUS_TRUSTED_PROXY_COUNT is set,
    taking the rightmost hop not appended by a trusted proxy. Otherwise the
    socket peer address is used, so clients cannot spoof their way past
    rate limits by sending forged headers directly.
    """
    direct = request.client.host if request.client else None
    if settings.trusted_proxy_count < 1:
        return direct
    header = request.headers.get("X-Forwarded-For")
    if not header:
        return direct
    hops = [hop.strip() for hop in header.split(",") if hop.strip()]
    if len(hops) < settings.trusted_proxy_count:
        return direct
    return hops[-settings.trusted_proxy_count]


@router.post("/login", response_model=AuthSessionResponse)
def login(
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
        client_ip=client_ip(request, settings),
    )
    _set_session_cookie(response, settings, result.session_token)
    return AuthSessionResponse(
        user=_to_user_response(result.user, result.default_route),
        csrf_token=result.session.csrf_token,
    )


@router.post("/register", response_model=RegistrationSubmitResponse, status_code=202)
def register(
    payload: RegistrationSubmitRequest,
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    registration_service: Annotated[RegistrationService, Depends(get_registration_service)],
) -> RegistrationSubmitResponse:
    auth_service.throttle_source(client_ip(request, settings))
    registration_service.submit(
        payload.username,
        payload.display_name,
        payload.justification,
        payload.password,
    )
    return RegistrationSubmitResponse(status="pending")


@router.post("/logout", status_code=204)
def logout(
    request: Request,
    response: Response,
    settings: Annotated[Settings, Depends(get_settings)],
    authenticated: Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> None:
    session_id = request.cookies.get(settings.session_cookie_name)
    auth_service.logout(session_id or "")
    _clear_session_cookie(response, settings)


@router.get("/me", response_model=AuthSessionResponse)
def me(
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
def rotate_session(
    request: Request,
    response: Response,
    settings: Annotated[Settings, Depends(get_settings)],
    authenticated: Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> AuthSessionResponse:
    session_id = request.cookies.get(settings.session_cookie_name)
    session_token, rotated = auth_service.rotate_session(session_id or "")
    _set_session_cookie(response, settings, session_token)
    return AuthSessionResponse(
        user=_to_user_response(
            authenticated.user,
            default_route_for_roles(authenticated.user.roles),
        ),
        csrf_token=rotated.csrf_token,
    )


@router.post("/password", response_model=AuthSessionResponse)
def change_password(
    payload: PasswordChangeRequest,
    request: Request,
    response: Response,
    settings: Annotated[Settings, Depends(get_settings)],
    authenticated: Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> AuthSessionResponse:
    session_id = request.cookies.get(settings.session_cookie_name)
    result = auth_service.change_password(
        session_id,
        payload.current_password,
        payload.new_password,
    )
    _set_session_cookie(response, settings, result.session_token)
    return AuthSessionResponse(
        user=_to_user_response(result.user, result.default_route),
        csrf_token=result.session.csrf_token,
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
        password_reset_required=user.password_reset_required,
    )
