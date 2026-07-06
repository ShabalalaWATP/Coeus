from collections.abc import Awaitable, Callable
from uuid import uuid4

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from coeus.api.routes.access import router as access_router
from coeus.api.routes.admin import router as admin_router
from coeus.api.routes.analyst import router as analyst_router
from coeus.api.routes.analytics import router as analytics_router
from coeus.api.routes.audit import router as audit_router
from coeus.api.routes.auth import router as auth_router
from coeus.api.routes.feedback import router as feedback_router
from coeus.api.routes.health import router as health_router
from coeus.api.routes.notifications import router as notifications_router
from coeus.api.routes.qc import router as qc_router
from coeus.api.routes.rfi_search import router as rfi_search_router
from coeus.api.routes.routing import router as routing_router
from coeus.api.routes.store import router as store_router
from coeus.api.routes.tickets import router as tickets_router
from coeus.core.config import Settings
from coeus.core.errors import AppError, app_error_handler, unhandled_exception_handler
from coeus.core.logging import configure_logging, get_logger
from coeus.core.security import apply_security_headers
from coeus.repositories.access import SeedAccessRepository
from coeus.repositories.auth import LoginAttemptRepository, SeedUserRepository, SessionRepository
from coeus.repositories.registration import RegistrationRepository
from coeus.services.access import build_access_services
from coeus.services.ai_models import AiModelService
from coeus.services.analyst_workflow import build_analyst_workflow_service
from coeus.services.audit import AuditLog
from coeus.services.auth import AuthService
from coeus.services.feedback_analytics import build_feedback_analytics_service
from coeus.services.notifications import NotificationService
from coeus.services.passwords import PasswordHasher
from coeus.services.product_release import ProductReleaseService
from coeus.services.quality_control import build_quality_control_service
from coeus.services.registration import RegistrationService
from coeus.services.rfi_search import build_rfi_search_service
from coeus.services.routing import build_routing_service
from coeus.services.store import build_store_services
from coeus.services.ticket_collaborators import TicketCollaboratorService
from coeus.services.tickets import build_ticket_services

logger = get_logger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or Settings()
    resolved_settings.require_runtime_security()
    configure_logging(resolved_settings.log_level)

    app = FastAPI(
        title="Istari API",
        version="0.1.0",
        description="Secure intelligence tasking and product orchestration API.",
    )
    app.state.settings = resolved_settings
    password_hasher = PasswordHasher(resolved_settings)
    user_repository = SeedUserRepository(resolved_settings, password_hasher)
    access_repository = SeedAccessRepository(user_repository)
    audit_log = AuditLog(max_events=resolved_settings.audit_log_max_events)
    app.state.auth_service = AuthService(
        settings=resolved_settings,
        users=user_repository,
        sessions=SessionRepository(),
        login_attempts=LoginAttemptRepository(
            max_entries=resolved_settings.login_attempt_max_entries
        ),
        password_hasher=password_hasher,
        audit_log=audit_log,
    )
    app.state.registration_service = RegistrationService(
        settings=resolved_settings,
        users=user_repository,
        registrations=RegistrationRepository(),
        password_hasher=password_hasher,
        audit_log=audit_log,
    )
    app.state.access_services = build_access_services(
        access_repository,
        audit_log,
    )
    app.state.store_services = build_store_services(access_repository, audit_log)
    app.state.ticket_services = build_ticket_services(audit_log)
    app.state.ticket_collaborator_service = TicketCollaboratorService(
        users=user_repository,
        tickets=app.state.ticket_services.tickets,
        audit_log=audit_log,
    )
    app.state.ai_model_service = AiModelService(resolved_settings, audit_log)
    app.state.rfi_search_service = build_rfi_search_service(
        app.state.ticket_services,
        app.state.store_services,
        access_repository,
        audit_log,
    )
    app.state.routing_service = build_routing_service(app.state.ticket_services, audit_log)
    app.state.analyst_workflow_service = build_analyst_workflow_service(
        app.state.ticket_services,
        app.state.store_services,
        access_repository,
        audit_log,
    )
    app.state.quality_control_service = build_quality_control_service(
        app.state.ticket_services,
        app.state.store_services,
        access_repository,
        audit_log,
    )
    app.state.notification_service = NotificationService(audit_log)
    app.state.product_release_service = ProductReleaseService(
        tickets=app.state.ticket_services,
        store=app.state.store_services,
        access=access_repository,
        notifications=app.state.notification_service,
        audit_log=audit_log,
    )
    app.state.feedback_analytics_service = build_feedback_analytics_service(
        app.state.ticket_services,
        app.state.store_services,
        audit_log,
    )

    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=resolved_settings.allowed_cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID", "X-CSRF-Token"],
    )

    @app.middleware("http")
    async def request_context_middleware(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        apply_security_headers(response)
        logger.info("request_completed", extra={"request_id": request_id})
        return response

    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(admin_router, prefix="/api/v1")
    app.include_router(audit_router, prefix="/api/v1")
    app.include_router(access_router, prefix="/api/v1")
    app.include_router(store_router, prefix="/api/v1")
    app.include_router(tickets_router, prefix="/api/v1")
    app.include_router(rfi_search_router, prefix="/api/v1")
    app.include_router(routing_router, prefix="/api/v1")
    app.include_router(analyst_router, prefix="/api/v1")
    app.include_router(qc_router, prefix="/api/v1")
    app.include_router(feedback_router, prefix="/api/v1")
    app.include_router(analytics_router, prefix="/api/v1")
    app.include_router(notifications_router, prefix="/api/v1")
    app.include_router(health_router, prefix="/api/v1")
    return app


app = create_app()
