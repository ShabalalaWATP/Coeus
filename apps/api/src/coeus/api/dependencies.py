from collections.abc import Callable
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, Header, Request

from coeus.core.config import Settings
from coeus.core.errors import AppError
from coeus.core.permissions import Permission
from coeus.db.session import DatabaseReadinessChecker
from coeus.domain.auth import AuthenticatedSession
from coeus.services.auth import AuthService


@lru_cache
def get_settings() -> Settings:
    return Settings()


def get_readiness_checker(
    settings: Annotated[Settings, Depends(get_settings)],
) -> DatabaseReadinessChecker:
    return DatabaseReadinessChecker(settings.database_url)


def get_request_id(request: Request) -> str:
    return str(getattr(request.state, "request_id", "unknown"))


def get_auth_service(request: Request) -> AuthService:
    auth_service = getattr(request.app.state, "auth_service", None)
    if not isinstance(auth_service, AuthService):
        raise AppError(500, "auth_not_configured", "Authentication service is not configured.")
    return auth_service


def get_current_session(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> AuthenticatedSession:
    session_id = request.cookies.get(settings.session_cookie_name)
    return auth_service.require_session(session_id)


def get_csrf_validated_session(
    settings: Annotated[Settings, Depends(get_settings)],
    authenticated: Annotated[AuthenticatedSession, Depends(get_current_session)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    csrf_token: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
) -> AuthenticatedSession:
    if settings.csrf_header_name != "X-CSRF-Token":
        raise AppError(500, "csrf_header_misconfigured", "CSRF header is misconfigured.")
    auth_service.require_csrf(authenticated, csrf_token)
    return authenticated


def require_permission(permission: Permission) -> Callable[..., AuthenticatedSession]:
    def dependency(
        authenticated: Annotated[AuthenticatedSession, Depends(get_current_session)],
        auth_service: Annotated[AuthService, Depends(get_auth_service)],
    ) -> AuthenticatedSession:
        auth_service.require_permission(authenticated, permission)
        return authenticated

    return dependency
