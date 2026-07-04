from collections.abc import Awaitable, Callable
from uuid import uuid4

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from coeus.api.routes.access import router as access_router
from coeus.api.routes.admin import router as admin_router
from coeus.api.routes.audit import router as audit_router
from coeus.api.routes.auth import router as auth_router
from coeus.api.routes.health import router as health_router
from coeus.core.config import Settings
from coeus.core.errors import AppError, app_error_handler, unhandled_exception_handler
from coeus.core.logging import configure_logging, get_logger
from coeus.core.security import apply_security_headers
from coeus.repositories.access import SeedAccessRepository
from coeus.repositories.auth import LoginAttemptRepository, SeedUserRepository, SessionRepository
from coeus.services.access import build_access_services
from coeus.services.audit import AuditLog
from coeus.services.auth import AuthService
from coeus.services.passwords import PasswordHasher

logger = get_logger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or Settings()
    configure_logging(resolved_settings.log_level)

    app = FastAPI(
        title="Coeus API",
        version="0.1.0",
        description="Secure intelligence tasking and product orchestration API.",
    )
    app.state.settings = resolved_settings
    password_hasher = PasswordHasher(resolved_settings)
    user_repository = SeedUserRepository(resolved_settings, password_hasher)
    audit_log = AuditLog()
    app.state.auth_service = AuthService(
        settings=resolved_settings,
        users=user_repository,
        sessions=SessionRepository(),
        login_attempts=LoginAttemptRepository(),
        password_hasher=password_hasher,
        audit_log=audit_log,
    )
    app.state.access_services = build_access_services(
        SeedAccessRepository(user_repository),
        audit_log,
    )

    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=resolved_settings.allowed_cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
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
    app.include_router(health_router, prefix="/api/v1")
    return app


app = create_app()
