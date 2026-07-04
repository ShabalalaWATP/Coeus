from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from coeus.api.dependencies import get_readiness_checker, get_request_id, get_settings
from coeus.core.config import Settings
from coeus.db.session import DatabaseReadinessChecker
from coeus.schemas.health import ComponentStatus, HealthResponse, ReadinessResponse

router = APIRouter(tags=["health"])


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
