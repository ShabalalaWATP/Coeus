"""Reviewed accountable-owner handover routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from coeus.api.dependencies import get_csrf_validated_session
from coeus.api.organisation_dependencies import get_work_package_handovers
from coeus.api.work_package_handover_contracts import (
    call_handover,
    handover_command,
    handover_request,
    handover_result,
)
from coeus.domain.auth import AuthenticatedSession
from coeus.schemas.work_package_handovers import (
    HandoverWorkPackageCommandPayload,
    WorkPackageHandoverPayload,
    WorkPackageHandoverPreviewResponse,
    WorkPackageHandoverResultResponse,
)
from coeus.services.work_package_handovers import WorkPackageHandoverService

router = APIRouter(
    prefix="/organisation/workspaces/{unit_id}/work-packages/{package_id}/handovers",
    tags=["work package handovers"],
)
SessionDep = Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)]
HandoverDep = Annotated[WorkPackageHandoverService, Depends(get_work_package_handovers)]


@router.post("/previews", response_model=WorkPackageHandoverPreviewResponse)
async def preview_work_package_handover(
    unit_id: UUID,
    package_id: UUID,
    payload: WorkPackageHandoverPayload,
    authenticated: SessionDep,
    service: HandoverDep,
) -> WorkPackageHandoverPreviewResponse:
    preview = call_handover(
        lambda: service.preview(
            authenticated.user.user_id,
            handover_request(unit_id, package_id, payload),
        )
    )
    return WorkPackageHandoverPreviewResponse(**vars(preview))


@router.post("/commands", response_model=WorkPackageHandoverResultResponse)
async def execute_work_package_handover(
    unit_id: UUID,
    package_id: UUID,
    payload: HandoverWorkPackageCommandPayload,
    authenticated: SessionDep,
    service: HandoverDep,
) -> WorkPackageHandoverResultResponse:
    command = call_handover(
        lambda: handover_command(unit_id, package_id, payload, authenticated.user.user_id)
    )
    return handover_result(call_handover(lambda: service.execute(command)))
