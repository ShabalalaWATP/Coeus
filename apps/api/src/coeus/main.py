from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
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
from coeus.api.routes.similar_requests import router as similar_requests_router
from coeus.api.routes.store import router as store_router
from coeus.api.routes.store_files import router as store_files_router
from coeus.api.routes.tickets import router as tickets_router
from coeus.api.routes.users_admin import router as users_admin_router
from coeus.core.config import Settings
from coeus.core.errors import AppError, app_error_handler, unhandled_exception_handler
from coeus.core.logging import configure_logging, get_logger
from coeus.core.security import apply_security_headers
from coeus.db.session import dispose_readiness_engines
from coeus.persistence.factory import build_state_store
from coeus.repositories.access import SeedAccessRepository
from coeus.repositories.auth import LoginAttemptRepository, SeedUserRepository, SessionRepository
from coeus.repositories.registration import RegistrationRepository
from coeus.services.access import build_access_services
from coeus.services.ai_models import AiModelService
from coeus.services.analyst_workflow import build_analyst_workflow_service
from coeus.services.asset_tokens import AssetTokenService
from coeus.services.audit import AuditLog
from coeus.services.auth import AuthService
from coeus.services.email_delivery import build_email_provider
from coeus.services.embeddings import build_embedding_service
from coeus.services.feedback_analytics import build_feedback_analytics_service
from coeus.services.notifications import NotificationService
from coeus.services.object_storage import LocalObjectStorage, seed_store_asset_placeholders
from coeus.services.passwords import PasswordHasher
from coeus.services.product_release import ProductReleaseService
from coeus.services.quality_control import build_quality_control_service
from coeus.services.registration import RegistrationService
from coeus.services.rfi_search import build_rfi_search_service
from coeus.services.routing import build_routing_service
from coeus.services.similar_requests import SimilarRequestService
from coeus.services.store_builder import build_store_services
from coeus.services.ticket_builder import build_ticket_services
from coeus.services.ticket_collaborators import TicketCollaboratorService
from coeus.services.ticket_lifecycle import TicketLifecycleService
from coeus.services.user_admin import UserAdminService

logger = get_logger(__name__)


@asynccontextmanager
async def _lifespan(_app: FastAPI) -> AsyncIterator[None]:
    yield
    await dispose_readiness_engines()


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or Settings()
    resolved_settings.require_runtime_security()
    configure_logging(resolved_settings.log_level)

    app = FastAPI(
        title="Istari API",
        version="0.1.0",
        description="Secure intelligence tasking and product orchestration API.",
        lifespan=_lifespan,
    )
    app.state.settings = resolved_settings
    app.state.state_store = build_state_store(resolved_settings)
    app.state.asset_token_service = AssetTokenService(resolved_settings.asset_token_secret)
    app.state.object_storage = LocalObjectStorage(resolved_settings.local_object_storage_path)
    password_hasher = PasswordHasher(resolved_settings)
    user_repository = SeedUserRepository(resolved_settings, password_hasher, app.state.state_store)
    session_repository = SessionRepository(app.state.state_store)
    access_repository = SeedAccessRepository(user_repository, app.state.state_store)
    audit_log = AuditLog(
        max_events=resolved_settings.audit_log_max_events,
        state_store=app.state.state_store,
    )
    login_attempts = LoginAttemptRepository(max_entries=resolved_settings.login_attempt_max_entries)
    app.state.auth_service = AuthService(
        settings=resolved_settings,
        users=user_repository,
        sessions=session_repository,
        login_attempts=login_attempts,
        password_hasher=password_hasher,
        audit_log=audit_log,
    )
    app.state.registration_service = RegistrationService(
        settings=resolved_settings,
        users=user_repository,
        registrations=RegistrationRepository(app.state.state_store),
        password_hasher=password_hasher,
        audit_log=audit_log,
    )
    app.state.access_services = build_access_services(
        access_repository,
        audit_log,
    )
    app.state.ai_model_service = AiModelService(
        resolved_settings,
        audit_log,
        app.state.state_store,
    )
    app.state.embedding_service = build_embedding_service(
        resolved_settings,
        app.state.ai_model_service,
    )
    app.state.store_services = build_store_services(
        access_repository,
        audit_log,
        app.state.asset_token_service,
        app.state.state_store,
        app.state.embedding_service,
    )
    app.state.ai_model_service.set_embedded_product_count_provider(
        app.state.store_services.repository.embedded_product_count
    )
    seed_store_asset_placeholders(
        app.state.object_storage,
        app.state.store_services.repository.list_products(),
    )
    app.state.ticket_services = build_ticket_services(
        resolved_settings,
        audit_log,
        app.state.state_store,
        app.state.ai_model_service,
    )
    app.state.ticket_collaborator_service = TicketCollaboratorService(
        users=user_repository,
        tickets=app.state.ticket_services.tickets,
        audit_log=audit_log,
    )
    app.state.ticket_lifecycle_service = TicketLifecycleService(
        tickets=app.state.ticket_services.tickets,
        audit_log=audit_log,
    )
    app.state.similar_request_service = SimilarRequestService(
        app.state.ticket_services,
        audit_log,
        app.state.embedding_service,
    )
    app.state.user_admin_service = UserAdminService(
        users=user_repository,
        sessions=session_repository,
        login_attempts=login_attempts,
        password_hasher=password_hasher,
        audit_log=audit_log,
    )
    app.state.rfi_search_service = build_rfi_search_service(
        app.state.ticket_services,
        app.state.store_services,
        access_repository,
        audit_log,
        app.state.embedding_service,
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
        app.state.object_storage,
    )
    app.state.notification_service = NotificationService(
        audit_log,
        app.state.state_store,
        build_email_provider(resolved_settings),
    )
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
        allow_headers=[
            "Authorization",
            "Content-Type",
            "X-Request-ID",
            "X-CSRF-Token",
            "X-Asset-Token",
        ],
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
        apply_security_headers(response, secure_transport=resolved_settings.secure_cookies)
        logger.info("request_completed", extra={"request_id": request_id})
        return response

    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(admin_router, prefix="/api/v1")
    app.include_router(users_admin_router, prefix="/api/v1")
    app.include_router(audit_router, prefix="/api/v1")
    app.include_router(access_router, prefix="/api/v1")
    app.include_router(store_router, prefix="/api/v1")
    app.include_router(store_files_router, prefix="/api/v1")
    app.include_router(tickets_router, prefix="/api/v1")
    app.include_router(rfi_search_router, prefix="/api/v1")
    app.include_router(similar_requests_router, prefix="/api/v1")
    app.include_router(routing_router, prefix="/api/v1")
    app.include_router(analyst_router, prefix="/api/v1")
    app.include_router(qc_router, prefix="/api/v1")
    app.include_router(feedback_router, prefix="/api/v1")
    app.include_router(analytics_router, prefix="/api/v1")
    app.include_router(notifications_router, prefix="/api/v1")
    app.include_router(health_router, prefix="/api/v1")
    return app


app = create_app()
