"""QC domain-to-API response mapping."""

from coeus.api.presenters.routing import priority_assessment_response
from coeus.domain.qc import FeedbackRequest, ProductIndexRecord, QcChecklistItem, QcDecision
from coeus.domain.store import StoreProduct
from coeus.domain.tickets import (
    DraftProductAsset,
    DraftProductVersion,
    ProductDissemination,
    TicketRecord,
)
from coeus.schemas.qc import (
    QcChecklistItemResponse,
    QcDecisionResponse,
    QcDisseminationResponse,
    QcDraftAssetResponse,
    QcDraftResponse,
    QcFeedbackRequestResponse,
    QcIndexRecordResponse,
    QcProductResponse,
    QcProductSummaryResponse,
)
from coeus.services.qc_records import QC_CHECKLIST_KEYS
from coeus.services.store import StoreServices


def product_response(ticket: TicketRecord, store: StoreServices) -> QcProductResponse:
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
        priority_assessment=priority_assessment_response(ticket),
        required_output_format=intake.required_output_format,
        checklist_keys=list(QC_CHECKLIST_KEYS),
        latest_draft=draft_response(ticket.draft_products[-1]) if ticket.draft_products else None,
        manager_notes=[decision.reason for decision in ticket.manager_decisions],
        decisions=[decision_response(item) for item in ticket.qc_decisions],
        index_records=[index_response(item) for item in ticket.product_index_records],
        disseminations=[dissemination_response(item) for item in ticket.disseminations],
        feedback_requests=[feedback_response(item) for item in ticket.feedback_requests],
        ingested_product=_ingested_product(ticket, store),
    )


def draft_response(draft: DraftProductVersion) -> QcDraftResponse:
    return QcDraftResponse(
        version_id=draft.version_id,
        version_number=draft.version_number,
        title=draft.title,
        summary=draft.summary,
        product_type=draft.product_type,
        content=draft.content,
        created_by_user_id=draft.created_by_user_id,
        created_at=draft.created_at,
        assets=[asset_response(asset) for asset in draft.assets],
    )


def asset_response(asset: DraftProductAsset) -> QcDraftAssetResponse:
    return QcDraftAssetResponse(
        asset_id=asset.asset_id,
        name=asset.name,
        asset_type=asset.asset_type,
        mime_type=asset.mime_type,
        size_bytes=asset.size_bytes,
        sha256=asset.sha256,
    )


def decision_response(decision: QcDecision) -> QcDecisionResponse:
    return QcDecisionResponse(
        decision_id=decision.decision_id,
        status=decision.status.value,
        reason=decision.reason,
        reviewer_user_id=decision.reviewer_user_id,
        checklist=[checklist_response(item) for item in decision.checklist],
        created_at=decision.created_at,
    )


def checklist_response(item: QcChecklistItem) -> QcChecklistItemResponse:
    return QcChecklistItemResponse(key=item.key, passed=item.passed)


def index_response(record: ProductIndexRecord) -> QcIndexRecordResponse:
    return QcIndexRecordResponse(
        index_id=record.index_id,
        product_id=record.product_id,
        status=record.status.value,
        summary=record.summary,
        created_at=record.created_at,
    )


def dissemination_response(record: ProductDissemination) -> QcDisseminationResponse:
    return QcDisseminationResponse(
        dissemination_id=record.dissemination_id,
        product_id=record.product_id,
        recipient_user_id=record.recipient_user_id,
        created_at=record.created_at,
    )


def feedback_response(record: FeedbackRequest) -> QcFeedbackRequestResponse:
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
    if not ticket.product_index_records:
        return None
    product = store.repository.get_product(ticket.product_index_records[-1].product_id)
    return product_summary(product) if product is not None else None


def product_summary(product: StoreProduct) -> QcProductSummaryResponse:
    return QcProductSummaryResponse(
        product_id=product.product_id,
        reference=product.reference,
        title=product.metadata.title,
        status=product.metadata.status.value,
        acg_ids=list(product.metadata.acg_ids),
    )
