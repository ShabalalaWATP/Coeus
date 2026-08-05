"""Admin-only read-only organisation cutover readiness."""

from typing import Annotated

from fastapi import APIRouter, Depends

from coeus.api.organisation_dependencies import (
    get_cutover_readiness,
    get_organisation_admin_session,
)
from coeus.domain.auth import AuthenticatedSession
from coeus.schemas.cutover_readiness import (
    CutoverReadinessCheckResponse,
    CutoverReadinessResponse,
)
from coeus.services.cutover_readiness import CutoverReadinessService

router = APIRouter(prefix="/admin/organisation", tags=["organisation administration"])


@router.get("/cutover-readiness", response_model=CutoverReadinessResponse)
def get_cutover_readiness_route(
    _: Annotated[AuthenticatedSession, Depends(get_organisation_admin_session)],
    service: Annotated[CutoverReadinessService, Depends(get_cutover_readiness)],
) -> CutoverReadinessResponse:
    report = service.report()
    return CutoverReadinessResponse(
        ready=report.ready,
        checks=[CutoverReadinessCheckResponse(**vars(item)) for item in report.checks],
    )
