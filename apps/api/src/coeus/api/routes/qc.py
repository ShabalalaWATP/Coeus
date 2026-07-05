from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from coeus.api.dependencies import (
    get_csrf_validated_session,
    get_current_session,
    get_quality_control_service,
    get_store_services,
)
from coeus.domain.auth import AuthenticatedSession
from coeus.domain.qc import FeedbackRequest, ProductIndexRecord, QcChecklistItem, QcDecision
from coeus.domain.store import StoreProduct
from coeus.domain.tickets import (
    DraftProductAsset,
    DraftProductVersion,
    ProductDissemination,
    TicketRecord,
)
from coeus.schemas.qc import (
    QcApprovalRequest,
    QcChecklistItemResponse,
    QcDecisionResponse,
    QcDisseminationResponse,
    QcDraftAssetResponse,
    QcDraftResponse,
    QcFeedbackRequestResponse,
    QcIndexRecordResponse,
    QcProductResponse,
    QcProductSummaryResponse,
    QcQueueResponse,
    QcRejectRequest,
)
from coeus.services.qc_records import QC_CHECKLIST_KEYS
from coeus.services.quality_control import QcApprovalInput, QualityControlService
from coeus.services.store import StoreServices

router = APIRouter(prefix="/qc", tags=["qc"])


@router.get("/queue", response_model=QcQueueResponse)
async def qc_queue(
    authenticated: Annotated[AuthenticatedSession, Depends(get_current_session)],
    qc: Annotated[QualityControlService, Depends(get_quality_control_service)],
    store: Annotated[StoreServices, Depends(get_store_services)],
) -> QcQueueResponse:
    return QcQueueResponse(
        products=[_product_response(ticket, store) for ticket in qc.queue(authenticated.user)]
    )


@router.get("/products/{ticket_id}", response_model=QcProductResponse)
async def qc_product(
    ticket_id: UUID,
    authenticated: Annotated[AuthenticatedSession, Depends(get_current_session)],
    qc: Annotated[QualityControlService, Depends(get_quality_control_service)],
    store: Annotated[StoreServices, Depends(get_store_services)],
) -> QcProductResponse:
    return _product_response(qc.details(authenticated.user, ticket_id), store)


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
    return _product_response(approved, store)


@router.post("/products/{ticket_id}/reject", response_model=QcProductResponse)
async def reject_qc_product(
    ticket_id: UUID,
    payload: QcRejectRequest,
    authenticated: Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)],
    qc: Annotated[QualityControlService, Depends(get_quality_control_service)],
    store: Annotated[StoreServices, Depends(get_store_services)],
) -> QcProductResponse:
    return _product_response(qc.reject(authenticated.user, ticket_id, payload.reason), store)


def _product_response(ticket: TicketRecord, store: StoreServices) -> QcProductResponse:
    intake = ticket.intake
    return QcProductResponse(
        ticket_id=ticket.ticket_id,
        reference=ticket.reference,
        requester_user_id=ticket.requester_user_id,
        state=ticket.state.value,
        title=intake.title or "Untitled requirement",
        operational_question=intake.operational_question,
        area_or_region=intake.area_or_region,
        priority=intake.priority,
        required_output_format=intake.required_output_format,
        checklist_keys=list(QC_CHECKLIST_KEYS),
        latest_draft=_draft_response(ticket.draft_products[-1]) if ticket.draft_products else None,
        manager_notes=[decision.reason for decision in ticket.manager_decisions],
        decisions=[_decision_response(item) for item in ticket.qc_decisions],
        index_records=[_index_response(item) for item in ticket.product_index_records],
        disseminations=[_dissemination_response(item) for item in ticket.disseminations],
        feedback_requests=[_feedback_response(item) for item in ticket.feedback_requests],
        ingested_product=_ingested_product(ticket, store),
    )


def _draft_response(draft: DraftProductVersion) -> QcDraftResponse:
    return QcDraftResponse(
        version_id=draft.version_id,
        version_number=draft.version_number,
        title=draft.title,
        summary=draft.summary,
        product_type=draft.product_type,
        content=draft.content,
        created_by_user_id=draft.created_by_user_id,
        created_at=draft.created_at,
        assets=[_asset_response(asset) for asset in draft.assets],
    )


def _asset_response(asset: DraftProductAsset) -> QcDraftAssetResponse:
    return QcDraftAssetResponse(
        asset_id=asset.asset_id,
        name=asset.name,
        asset_type=asset.asset_type,
        mime_type=asset.mime_type,
        size_bytes=asset.size_bytes,
        sha256=asset.sha256,
    )


def _decision_response(decision: QcDecision) -> QcDecisionResponse:
    return QcDecisionResponse(
        decision_id=decision.decision_id,
        status=decision.status.value,
        reason=decision.reason,
        reviewer_user_id=decision.reviewer_user_id,
        checklist=[_checklist_response(item) for item in decision.checklist],
        created_at=decision.created_at,
    )


def _checklist_response(item: QcChecklistItem) -> QcChecklistItemResponse:
    return QcChecklistItemResponse(key=item.key, passed=item.passed)


def _index_response(record: ProductIndexRecord) -> QcIndexRecordResponse:
    return QcIndexRecordResponse(
        index_id=record.index_id,
        product_id=record.product_id,
        status=record.status.value,
        summary=record.summary,
        created_at=record.created_at,
    )


def _dissemination_response(record: ProductDissemination) -> QcDisseminationResponse:
    return QcDisseminationResponse(
        dissemination_id=record.dissemination_id,
        product_id=record.product_id,
        recipient_user_id=record.recipient_user_id,
        created_at=record.created_at,
    )


def _feedback_response(record: FeedbackRequest) -> QcFeedbackRequestResponse:
    return QcFeedbackRequestResponse(
        request_id=record.request_id,
        product_id=record.product_id,
        requester_user_id=record.requester_user_id,
        status=record.status.value,
        created_at=record.created_at,
    )


def _ingested_product(
    ticket: TicketRecord, store: StoreServices
) -> QcProductSummaryResponse | None:
    if not ticket.disseminations:
        return None
    product = store.repository.get_product(ticket.disseminations[-1].product_id)
    return _product_summary(product) if product is not None else None


def _product_summary(product: StoreProduct) -> QcProductSummaryResponse:
    return QcProductSummaryResponse(
        product_id=product.product_id,
        reference=product.reference,
        title=product.metadata.title,
        status=product.metadata.status.value,
        acg_ids=list(product.metadata.acg_ids),
    )
