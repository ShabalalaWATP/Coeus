from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, Header, Request

from coeus.core.config import Settings
from coeus.core.errors import AppError
from coeus.core.permissions import Permission
from coeus.db.session import DatabaseReadinessChecker
from coeus.domain.auth import AuthenticatedSession
from coeus.services.access import AccessServices
from coeus.services.analyst_workflow import AnalystWorkflowService
from coeus.services.auth import AuthService
from coeus.services.quality_control import QualityControlService
from coeus.services.rfi_search import RfiSearchService
from coeus.services.routing import RoutingService
from coeus.services.store import StoreServices
from coeus.services.tickets import TicketServices


def get_settings(request: Request) -> Settings:
    settings = getattr(request.app.state, "settings", None)
    if not isinstance(settings, Settings):
        raise AppError(500, "settings_not_configured", "Application settings are not configured.")
    return settings


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


def get_access_services(request: Request) -> AccessServices:
    access_services = getattr(request.app.state, "access_services", None)
    if not isinstance(access_services, AccessServices):
        raise AppError(500, "access_not_configured", "Access services are not configured.")
    return access_services


def get_ticket_services(request: Request) -> TicketServices:
    ticket_services = getattr(request.app.state, "ticket_services", None)
    if not isinstance(ticket_services, TicketServices):
        raise AppError(500, "tickets_not_configured", "Ticket services are not configured.")
    return ticket_services


def get_store_services(request: Request) -> StoreServices:
    store_services = getattr(request.app.state, "store_services", None)
    if not isinstance(store_services, StoreServices):
        raise AppError(500, "store_not_configured", "Store services are not configured.")
    return store_services


def get_rfi_search_service(request: Request) -> RfiSearchService:
    rfi_search_service = getattr(request.app.state, "rfi_search_service", None)
    if not isinstance(rfi_search_service, RfiSearchService):
        raise AppError(500, "rfi_search_not_configured", "RFI search is not configured.")
    return rfi_search_service


def get_routing_service(request: Request) -> RoutingService:
    routing_service = getattr(request.app.state, "routing_service", None)
    if not isinstance(routing_service, RoutingService):
        raise AppError(500, "routing_not_configured", "Routing is not configured.")
    return routing_service


def get_analyst_workflow_service(request: Request) -> AnalystWorkflowService:
    analyst_service = getattr(request.app.state, "analyst_workflow_service", None)
    if not isinstance(analyst_service, AnalystWorkflowService):
        raise AppError(500, "analyst_not_configured", "Analyst workflow is not configured.")
    return analyst_service


def get_quality_control_service(request: Request) -> QualityControlService:
    qc_service = getattr(request.app.state, "quality_control_service", None)
    if not isinstance(qc_service, QualityControlService):
        raise AppError(500, "qc_not_configured", "Quality control is not configured.")
    return qc_service


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
