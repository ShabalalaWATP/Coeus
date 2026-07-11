from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, Header, Request

from coeus.core.config import Settings
from coeus.core.errors import AppError
from coeus.core.permissions import Permission
from coeus.db.session import DatabaseReadinessChecker, readiness_checker_for
from coeus.domain.auth import AuthenticatedSession
from coeus.repositories.teams import TeamRepository
from coeus.services.access import AccessServices
from coeus.services.ai_models import AiModelService
from coeus.services.analyst_assignment_service import AnalystAssignmentService
from coeus.services.analyst_workflow import AnalystWorkflowService
from coeus.services.asset_tokens import AssetTokenService
from coeus.services.auth import AuthService
from coeus.services.feedback_analytics import FeedbackAnalyticsService
from coeus.services.manager_approval import ManagerApprovalService
from coeus.services.manager_queue import ManagerQueueService
from coeus.services.notifications import NotificationService
from coeus.services.object_storage import ObjectStorage
from coeus.services.quality_control import QualityControlService
from coeus.services.registration import RegistrationService
from coeus.services.rfi_search import RfiSearchService
from coeus.services.routing import RoutingService
from coeus.services.similar_requests import SimilarRequestService
from coeus.services.store import StoreServices
from coeus.services.team_availability import TeamAvailabilityService, TeamCalendarService
from coeus.services.team_workspace import TeamWorkspaceService
from coeus.services.ticket_collaborators import TicketCollaboratorService
from coeus.services.ticket_lifecycle import TicketLifecycleService
from coeus.services.tickets import TicketServices
from coeus.services.user_admin import UserAdminService


def get_settings(request: Request) -> Settings:
    settings = getattr(request.app.state, "settings", None)
    if not isinstance(settings, Settings):
        raise AppError(500, "settings_not_configured", "Application settings are not configured.")
    return settings


def get_readiness_checker(
    settings: Annotated[Settings, Depends(get_settings)],
) -> DatabaseReadinessChecker:
    return readiness_checker_for(settings.database_url)


def get_request_id(request: Request) -> str:
    return str(getattr(request.state, "request_id", "unknown"))


def get_auth_service(request: Request) -> AuthService:
    auth_service = getattr(request.app.state, "auth_service", None)
    if not isinstance(auth_service, AuthService):
        raise AppError(500, "auth_not_configured", "Authentication service is not configured.")
    return auth_service


def get_ticket_collaborator_service(request: Request) -> TicketCollaboratorService:
    service = getattr(request.app.state, "ticket_collaborator_service", None)
    if not isinstance(service, TicketCollaboratorService):
        raise AppError(500, "collaborators_not_configured", "Collaborators are not configured.")
    return service


def get_ticket_lifecycle_service(request: Request) -> TicketLifecycleService:
    service = getattr(request.app.state, "ticket_lifecycle_service", None)
    if not isinstance(service, TicketLifecycleService):
        raise AppError(
            500, "ticket_lifecycle_not_configured", "Ticket lifecycle is not configured."
        )
    return service


def get_user_admin_service(request: Request) -> UserAdminService:
    service = getattr(request.app.state, "user_admin_service", None)
    if not isinstance(service, UserAdminService):
        raise AppError(500, "user_admin_not_configured", "User administration is not configured.")
    return service


def get_ai_model_service(request: Request) -> AiModelService:
    service = getattr(request.app.state, "ai_model_service", None)
    if not isinstance(service, AiModelService):
        raise AppError(500, "ai_models_not_configured", "AI model selection is not configured.")
    return service


def get_manager_approval_service(request: Request) -> ManagerApprovalService:
    service = getattr(request.app.state, "manager_approval_service", None)
    if not isinstance(service, ManagerApprovalService):
        raise AppError(500, "approval_not_configured", "Manager approval is not configured.")
    return service


def get_analyst_assignment_service(request: Request) -> AnalystAssignmentService:
    service = getattr(request.app.state, "analyst_assignment_service", None)
    if not isinstance(service, AnalystAssignmentService):
        raise AppError(500, "assignment_not_configured", "Analyst assignment is not configured.")
    return service


def get_notification_service(request: Request) -> NotificationService:
    service = getattr(request.app.state, "notification_service", None)
    if not isinstance(service, NotificationService):
        raise AppError(500, "notifications_not_configured", "Notifications are not configured.")
    return service


def get_registration_service(request: Request) -> RegistrationService:
    registration_service = getattr(request.app.state, "registration_service", None)
    if not isinstance(registration_service, RegistrationService):
        raise AppError(500, "registration_not_configured", "Registration is not configured.")
    return registration_service


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


def get_object_storage(request: Request) -> ObjectStorage:
    storage = getattr(request.app.state, "object_storage", None)
    if not isinstance(storage, ObjectStorage):
        raise AppError(500, "object_storage_not_configured", "Object storage is not configured.")
    return storage


def get_asset_token_service(request: Request) -> AssetTokenService:
    service = getattr(request.app.state, "asset_token_service", None)
    if not isinstance(service, AssetTokenService):
        raise AppError(500, "asset_tokens_not_configured", "Asset tokens are not configured.")
    return service


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


def get_manager_queue_service(request: Request) -> ManagerQueueService:
    service = getattr(request.app.state, "manager_queue_service", None)
    if not isinstance(service, ManagerQueueService):
        raise AppError(500, "manager_queue_not_configured", "Manager queues are not configured.")
    return service


def get_similar_request_service(request: Request) -> SimilarRequestService:
    service = getattr(request.app.state, "similar_request_service", None)
    if not isinstance(service, SimilarRequestService):
        raise AppError(
            500, "similar_requests_not_configured", "Similar requests are not configured."
        )
    return service


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


def get_team_workspace_service(request: Request) -> TeamWorkspaceService:
    service = getattr(request.app.state, "team_workspace_service", None)
    if not isinstance(service, TeamWorkspaceService):
        raise AppError(500, "teams_not_configured", "Team workspaces are not configured.")
    return service


def get_team_availability_service(request: Request) -> TeamAvailabilityService:
    service = getattr(request.app.state, "team_availability_service", None)
    if not isinstance(service, TeamAvailabilityService):
        raise AppError(500, "teams_not_configured", "Team availability is not configured.")
    return service


def get_team_calendar_service(request: Request) -> TeamCalendarService:
    service = getattr(request.app.state, "team_calendar_service", None)
    if not isinstance(service, TeamCalendarService):
        raise AppError(500, "teams_not_configured", "Team calendars are not configured.")
    return service


def get_team_repository(request: Request) -> TeamRepository:
    repository = getattr(request.app.state, "team_repository", None)
    if not isinstance(repository, TeamRepository):
        raise AppError(500, "teams_not_configured", "Team repository is not configured.")
    return repository


def get_feedback_analytics_service(request: Request) -> FeedbackAnalyticsService:
    service = getattr(request.app.state, "feedback_analytics_service", None)
    if not isinstance(service, FeedbackAnalyticsService):
        raise AppError(500, "feedback_analytics_not_configured", "Analytics is not configured.")
    return service


# Endpoints a user may still call while a forced password rotation is pending.
PASSWORD_RESET_ALLOWED_PATHS = frozenset(
    {
        "/api/v1/auth/me",
        "/api/v1/auth/logout",
        "/api/v1/auth/password",
    }
)


def get_current_session(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> AuthenticatedSession:
    session_id = request.cookies.get(settings.session_cookie_name)
    authenticated = auth_service.require_session(session_id)
    if (
        authenticated.user.password_reset_required
        and request.url.path not in PASSWORD_RESET_ALLOWED_PATHS
    ):
        raise AppError(
            403,
            "password_change_required",
            "Change the temporary password before using this endpoint.",
        )
    return authenticated


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
