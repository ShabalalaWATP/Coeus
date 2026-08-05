"""Two-manager cross-team workflow-leg transfer routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from coeus.api.dependencies import get_csrf_validated_session
from coeus.api.organisation_dependencies import get_workflow_leg_transfers
from coeus.api.workflow_leg_transfer_contracts import call_transfer, command, proposal
from coeus.domain.auth import AuthenticatedSession
from coeus.schemas.workflow_leg_transfers import (
    ProposeWorkflowLegTransferPayload,
    WorkflowLegTransferCommandPayload,
    WorkflowLegTransferPreviewResponse,
    WorkflowLegTransferProposalPayload,
    WorkflowLegTransferResultResponse,
)
from coeus.services.workflow_leg_transfers import WorkflowLegTransferService

router = APIRouter(prefix="/organisation/workflow-leg-transfers", tags=["workflow-leg transfers"])
SessionDep = Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)]
ServiceDep = Annotated[WorkflowLegTransferService, Depends(get_workflow_leg_transfers)]


@router.post(
    "/sources/{source_unit_id}/previews", response_model=WorkflowLegTransferPreviewResponse
)
async def preview_transfer(
    source_unit_id: UUID,
    payload: WorkflowLegTransferProposalPayload,
    authenticated: SessionDep,
    service: ServiceDep,
) -> WorkflowLegTransferPreviewResponse:
    result = call_transfer(
        lambda: service.preview(authenticated.user.user_id, proposal(source_unit_id, payload))
    )
    return WorkflowLegTransferPreviewResponse(**vars(result))


@router.post(
    "/sources/{source_unit_id}/proposals", response_model=WorkflowLegTransferResultResponse
)
async def propose_transfer(
    source_unit_id: UUID,
    payload: ProposeWorkflowLegTransferPayload,
    authenticated: SessionDep,
    service: ServiceDep,
) -> WorkflowLegTransferResultResponse:
    request = call_transfer(lambda: proposal(source_unit_id, payload.proposal))
    result = call_transfer(
        lambda: service.propose(
            authenticated.user.user_id,
            payload.command_id,
            payload.idempotency_key,
            request,
            payload.preview_hash,
        )
    )
    return WorkflowLegTransferResultResponse(**vars(result))


@router.post("/{transfer_id}/commands", response_model=WorkflowLegTransferResultResponse)
async def decide_transfer(
    transfer_id: UUID,
    payload: WorkflowLegTransferCommandPayload,
    authenticated: SessionDep,
    service: ServiceDep,
) -> WorkflowLegTransferResultResponse:
    request = call_transfer(lambda: command(transfer_id, authenticated.user.user_id, payload))
    result = call_transfer(lambda: service.decide(request))
    return WorkflowLegTransferResultResponse(**vars(result))
