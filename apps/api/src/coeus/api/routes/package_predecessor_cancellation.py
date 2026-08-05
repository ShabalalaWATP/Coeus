"""Explicit predecessor cancellation routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from coeus.api.dependencies import get_csrf_validated_session
from coeus.api.organisation_dependencies import get_predecessor_cancellation
from coeus.api.package_predecessor_cancellation_contracts import (
    call_cancellation,
    cancellation_command,
    cancellation_request,
    cancellation_result,
)
from coeus.domain.auth import AuthenticatedSession
from coeus.schemas.package_predecessor_cancellation import (
    CancelPredecessorCommandPayload,
    PredecessorCancellationPayload,
    PredecessorCancellationPreviewResponse,
    PredecessorCancellationResultResponse,
)
from coeus.services.package_predecessor_cancellation import PredecessorCancellationService

router = APIRouter(
    prefix="/organisation/workspaces/{unit_id}/work-packages/{package_id}/cancellation",
    tags=["work package cancellation"],
)
SessionDep = Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)]
CancellationDep = Annotated[PredecessorCancellationService, Depends(get_predecessor_cancellation)]


@router.post("/previews", response_model=PredecessorCancellationPreviewResponse)
async def preview_predecessor_cancellation(
    unit_id: UUID,
    package_id: UUID,
    payload: PredecessorCancellationPayload,
    authenticated: SessionDep,
    service: CancellationDep,
) -> PredecessorCancellationPreviewResponse:
    result = call_cancellation(
        lambda: service.preview(
            authenticated.user.user_id, cancellation_request(unit_id, package_id, payload)
        )
    )
    return PredecessorCancellationPreviewResponse(**vars(result))


@router.post("/commands", response_model=PredecessorCancellationResultResponse)
async def execute_predecessor_cancellation(
    unit_id: UUID,
    package_id: UUID,
    payload: CancelPredecessorCommandPayload,
    authenticated: SessionDep,
    service: CancellationDep,
) -> PredecessorCancellationResultResponse:
    command = call_cancellation(
        lambda: cancellation_command(unit_id, package_id, payload, authenticated.user.user_id)
    )
    return cancellation_result(call_cancellation(lambda: service.execute(command)))
