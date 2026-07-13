from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse, PlainTextResponse

from coeus.api.dependencies import (
    get_admission_metrics,
    get_readiness_checker,
    get_request_id,
    get_settings,
)
from coeus.core.config import Settings
from coeus.db.session import DatabaseReadinessChecker
from coeus.schemas.health import ComponentStatus, HealthResponse, ReadinessResponse
from coeus.services.admission_metrics import AdmissionMetrics

router = APIRouter(tags=["health"])


@router.get("/metrics", response_class=PlainTextResponse, include_in_schema=False)
async def metrics(
    registry: Annotated[AdmissionMetrics, Depends(get_admission_metrics)],
) -> PlainTextResponse:
    lines = ["# HELP coeus_admission_total Low-cardinality admission outcomes."]
    lines.append("# TYPE coeus_admission_total counter")
    for key, count in registry.snapshot().items():
        resource, outcome = key.split(".", 1)
        lines.append(f'coeus_admission_total{{resource="{resource}",outcome="{outcome}"}} {count}')
    return PlainTextResponse("\n".join(lines) + "\n", media_type="text/plain; version=0.0.4")


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
