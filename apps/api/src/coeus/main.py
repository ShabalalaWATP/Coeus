import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager, suppress
from uuid import uuid4

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from coeus.api.routes.access import router as access_router
from coeus.api.routes.admin import router as admin_router
from coeus.api.routes.analyst import router as analyst_router
from coeus.api.routes.analyst_files import router as analyst_files_router
from coeus.api.routes.analytics import router as analytics_router
from coeus.api.routes.audit import router as audit_router
from coeus.api.routes.auth import router as auth_router
from coeus.api.routes.customer_outcomes import router as customer_outcomes_router
from coeus.api.routes.feedback import router as feedback_router
from coeus.api.routes.health import router as health_router
from coeus.api.routes.notifications import router as notifications_router
from coeus.api.routes.qc import router as qc_router
from coeus.api.routes.rfi_search import router as rfi_search_router
from coeus.api.routes.routing import router as routing_router
from coeus.api.routes.search_admin import router as search_admin_router
from coeus.api.routes.similar_requests import router as similar_requests_router
from coeus.api.routes.store import router as store_router
from coeus.api.routes.store_files import router as store_files_router
from coeus.api.routes.store_previews import router as store_previews_router
from coeus.api.routes.teams import profile_router as profiles_router
from coeus.api.routes.teams import router as teams_router
from coeus.api.routes.tickets import router as tickets_router
from coeus.api.routes.users_admin import router as users_admin_router
from coeus.api.routes.voice import router as voice_router
from coeus.application.ports.outbox import OutboxDispatchPort
from coeus.composition import configure_application_state
from coeus.core.config import Settings
from coeus.core.errors import AppError, app_error_handler, unhandled_exception_handler
from coeus.core.logging import configure_logging, get_logger
from coeus.core.security import apply_security_headers
from coeus.db.session import dispose_readiness_engines

logger = get_logger(__name__)


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    stop = asyncio.Event()
    dispatcher = getattr(app.state, "outbox_dispatcher", None)
    task = (
        asyncio.create_task(_dispatch_outbox(app, dispatcher, stop))
        if dispatcher is not None
        else None
    )
    try:
        yield
    finally:
        stop.set()
        if task is not None:
            await task
        await dispose_readiness_engines()


async def _dispatch_outbox(
    app: FastAPI, dispatcher: OutboxDispatchPort, stop: asyncio.Event
) -> None:
    worker_id = uuid4()
    settings: Settings = app.state.settings
    while not stop.is_set():
        try:
            result = await asyncio.to_thread(
                dispatcher.dispatch, worker_id, limit=settings.outbox_batch_size
            )
            if result.claimed or result.dead_lettered:
                logger.info(
                    "outbox_dispatch_completed",
                    extra={
                        "claimed": result.claimed,
                        "delivered": result.delivered,
                        "failed": result.failed,
                        "dead_lettered": result.dead_lettered,
                    },
                )
        except Exception:
            logger.exception("outbox_dispatch_failed")
        with suppress(TimeoutError):
            await asyncio.wait_for(stop.wait(), timeout=settings.outbox_poll_seconds)


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
    configure_application_state(app, resolved_settings)

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
        expose_headers=["X-Voice-Session-Token"],
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
    app.include_router(search_admin_router, prefix="/api/v1")
    app.include_router(users_admin_router, prefix="/api/v1")
    app.include_router(audit_router, prefix="/api/v1")
    app.include_router(access_router, prefix="/api/v1")
    app.include_router(store_router, prefix="/api/v1")
    app.include_router(store_files_router, prefix="/api/v1")
    app.include_router(store_previews_router, prefix="/api/v1")
    app.include_router(tickets_router, prefix="/api/v1")
    app.include_router(customer_outcomes_router, prefix="/api/v1")
    app.include_router(rfi_search_router, prefix="/api/v1")
    app.include_router(similar_requests_router, prefix="/api/v1")
    app.include_router(routing_router, prefix="/api/v1")
    app.include_router(analyst_router, prefix="/api/v1")
    app.include_router(analyst_files_router, prefix="/api/v1")
    app.include_router(qc_router, prefix="/api/v1")
    app.include_router(feedback_router, prefix="/api/v1")
    app.include_router(analytics_router, prefix="/api/v1")
    app.include_router(notifications_router, prefix="/api/v1")
    app.include_router(teams_router, prefix="/api/v1")
    app.include_router(profiles_router, prefix="/api/v1")
    app.include_router(voice_router, prefix="/api/v1")
    app.include_router(health_router, prefix="/api/v1")
    return app


app = create_app()
