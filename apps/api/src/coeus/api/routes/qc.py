from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response

from coeus.api.dependencies import (
    get_csrf_validated_session,
    get_current_session,
    get_quality_control_service,
    get_store_services,
)
from coeus.api.presenters.qc import product_response, queue_item_response
from coeus.domain.auth import AuthenticatedSession
from coeus.schemas.qc import (
    QcApprovalRequest,
    QcProductResponse,
    QcQueueResponse,
    QcRejectRequest,
)
from coeus.services.quality_control import QcApprovalInput, QualityControlService
from coeus.services.store import StoreServices

router = APIRouter(prefix="/qc", tags=["qc"])


@router.get("/queue", response_model=QcQueueResponse)
async def qc_queue(
    authenticated: Annotated[AuthenticatedSession, Depends(get_current_session)],
    qc: Annotated[QualityControlService, Depends(get_quality_control_service)],
    store: Annotated[StoreServices, Depends(get_store_services)],
) -> QcQueueResponse:
    queue = qc.queue(authenticated.user)
    return QcQueueResponse(
        products=[product_response(ticket, store) for ticket in queue.assigned_products],
        items=[queue_item_response(item) for item in queue.items],
    )


@router.get("/products/{ticket_id}", response_model=QcProductResponse)
async def qc_product(
    ticket_id: UUID,
    authenticated: Annotated[AuthenticatedSession, Depends(get_current_session)],
    qc: Annotated[QualityControlService, Depends(get_quality_control_service)],
    store: Annotated[StoreServices, Depends(get_store_services)],
) -> QcProductResponse:
    return product_response(qc.details(authenticated.user, ticket_id), store)


@router.post("/products/{ticket_id}/claim", response_model=QcProductResponse)
async def claim_qc_product(
    ticket_id: UUID,
    authenticated: Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)],
    qc: Annotated[QualityControlService, Depends(get_quality_control_service)],
    store: Annotated[StoreServices, Depends(get_store_services)],
) -> QcProductResponse:
    claimed = qc.claim(authenticated.user, ticket_id)
    return product_response(qc.prepare_review(authenticated.user, claimed), store)


@router.delete("/products/{ticket_id}/claim", status_code=204)
async def release_qc_claim(
    ticket_id: UUID,
    authenticated: Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)],
    qc: Annotated[QualityControlService, Depends(get_quality_control_service)],
) -> Response:
    qc.release_claim(authenticated.user, ticket_id)
    return Response(status_code=204)


@router.post("/products/{ticket_id}/approve", response_model=QcProductResponse)
async def approve_qc_product(
    ticket_id: UUID,
    payload: QcApprovalRequest,
    authenticated: Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)],
    qc: Annotated[QualityControlService, Depends(get_quality_control_service)],
    store: Annotated[StoreServices, Depends(get_store_services)],
) -> QcProductResponse:
    approved = qc.approve(
        authenticated.user,
        ticket_id,
        QcApprovalInput(
            checklist=payload.checklist,
            classification_level=payload.classification_level,
            releasability=tuple(payload.releasability),
            handling_caveats=tuple(payload.handling_caveats),
            acg_ids=frozenset(payload.acg_ids),
            reason=payload.reason,
        ),
    )
    return product_response(approved, store)


@router.post("/products/{ticket_id}/reject", response_model=QcProductResponse)
async def reject_qc_product(
    ticket_id: UUID,
    payload: QcRejectRequest,
    authenticated: Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)],
    qc: Annotated[QualityControlService, Depends(get_quality_control_service)],
    store: Annotated[StoreServices, Depends(get_store_services)],
) -> QcProductResponse:
    return product_response(qc.reject(authenticated.user, ticket_id, payload.reason), store)
