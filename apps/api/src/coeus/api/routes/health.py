from hmac import compare_digest
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, PlainTextResponse

from coeus.api.dependencies import (
    get_admission_metrics,
    get_readiness_checker,
    get_request_id,
    get_settings,
)
from coeus.application.ports.outbox import OutboxDispatcherPort
from coeus.core.config import Settings
from coeus.core.logging import get_logger
from coeus.db.session import DatabaseReadinessChecker
from coeus.domain.outbox import OutboxStatus
from coeus.schemas.health import ComponentStatus, HealthResponse, ReadinessResponse
from coeus.services.admission_metrics import AdmissionMetrics

router = APIRouter(tags=["health"])
logger = get_logger(__name__)


@router.get("/metrics", response_class=PlainTextResponse, include_in_schema=False)
async def metrics(
    request: Request,
    registry: Annotated[AdmissionMetrics, Depends(get_admission_metrics)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> PlainTextResponse:
    _require_metrics_access(request, settings)
    lines = ["# HELP coeus_admission_total Low-cardinality admission outcomes."]
    lines.append("# TYPE coeus_admission_total counter")
    for key, count in registry.snapshot().items():
        resource, outcome = key.split(".", 1)
        lines.append(f'coeus_admission_total{{resource="{resource}",outcome="{outcome}"}} {count}')
    dispatcher: OutboxDispatcherPort | None = getattr(request.app.state, "outbox_dispatcher", None)
    configured = dispatcher is not None
    available = False
    status = OutboxStatus(0, 0, 0, None)
    if dispatcher is not None:
        try:
            snapshot = dispatcher.metrics_status()
        except Exception:
            logger.warning("outbox_metrics_snapshot_failed")
        else:
            if snapshot is not None:
                status = snapshot
                available = True
    lines.extend(_outbox_metric_lines(configured, available, status))
    return PlainTextResponse("\n".join(lines) + "\n", media_type="text/plain; version=0.0.4")


def _require_metrics_access(request: Request, settings: Settings) -> None:
    expected = settings.metrics_bearer_token
    if expected is None:
        if settings.environment in {"local", "test"}:
            return
        raise HTTPException(
            status_code=401,
            detail="Metrics authentication required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    scheme, separator, credential = request.headers.get("Authorization", "").partition(" ")
    valid = (
        separator == " " and scheme.casefold() == "bearer" and compare_digest(credential, expected)
    )
    if not valid:
        raise HTTPException(
            status_code=401,
            detail="Metrics authentication required.",
            headers={"WWW-Authenticate": "Bearer"},
        )


def _outbox_metric_lines(
    configured: bool, available: bool, status: OutboxStatus
) -> tuple[str, ...]:
    age = status.oldest_pending_age_seconds or 0
    return (
        "# HELP coeus_outbox_configured Whether durable outbox delivery is configured.",
        "# TYPE coeus_outbox_configured gauge",
        f"coeus_outbox_configured {int(configured)}",
        "# HELP coeus_outbox_available Whether a cached outbox status is available.",
        "# TYPE coeus_outbox_available gauge",
        f"coeus_outbox_available {int(available)}",
        "# HELP coeus_outbox_pending_messages Undelivered messages awaiting delivery.",
        "# TYPE coeus_outbox_pending_messages gauge",
        f"coeus_outbox_pending_messages {status.pending_count}",
        "# HELP coeus_outbox_retrying_messages Pending messages with a prior failure.",
        "# TYPE coeus_outbox_retrying_messages gauge",
        f"coeus_outbox_retrying_messages {status.retrying_count}",
        "# HELP coeus_outbox_dead_letter_messages Messages requiring operator recovery.",
        "# TYPE coeus_outbox_dead_letter_messages gauge",
        f"coeus_outbox_dead_letter_messages {status.dead_letter_count}",
        "# HELP coeus_outbox_oldest_pending_age_seconds Age of the oldest pending message.",
        "# TYPE coeus_outbox_oldest_pending_age_seconds gauge",
        f"coeus_outbox_oldest_pending_age_seconds {age}",
    )


@router.get("/health/live", response_model=HealthResponse)
async def liveness(
    settings: Annotated[Settings, Depends(get_settings)],
    request_id: Annotated[str, Depends(get_request_id)],
) -> HealthResponse:
    return HealthResponse(
        status="ok",
        service="coeus-api",
        environment=settings.environment,
        request_id=request_id,
    )


@router.get("/health/ready", response_model=ReadinessResponse)
async def readiness(
    settings: Annotated[Settings, Depends(get_settings)],
    checker: Annotated[DatabaseReadinessChecker, Depends(get_readiness_checker)],
    request_id: Annotated[str, Depends(get_request_id)],
) -> ReadinessResponse | JSONResponse:
    database_result = await checker.check()
    payload = ReadinessResponse(
        status="ready" if database_result.ready else "not_ready",
        service="coeus-api",
        environment=settings.environment,
        request_id=request_id,
        components=[
            ComponentStatus(
                name="postgresql",
                status="ready" if database_result.ready else "not_ready",
                detail=database_result.detail,
            )
        ],
    )
    if database_result.ready:
        return payload
    return JSONResponse(status_code=503, content=payload.model_dump())
