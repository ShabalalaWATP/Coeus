from collections.abc import Awaitable, Callable
from uuid import uuid4

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from coeus.api.routes.health import router as health_router
from coeus.core.config import Settings
from coeus.core.errors import AppError, app_error_handler, unhandled_exception_handler
from coeus.core.logging import configure_logging, get_logger
from coeus.core.security import apply_security_headers

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

    app.include_router(health_router, prefix="/api/v1")
    return app


app = create_app()
