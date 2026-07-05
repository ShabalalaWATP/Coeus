from datetime import UTC, datetime
from uuid import UUID, uuid4

from coeus.domain.qc import (
    FeedbackRequest,
    FeedbackRequestStatus,
    ProductIndexRecord,
    ProductIndexStatus,
    QcChecklistItem,
    QcDecision,
    QcDecisionStatus,
)
from coeus.domain.tickets import ProductDissemination

QC_CHECKLIST_KEYS = (
    "answers_customer_question",
    "sources_are_sufficient",
    "metadata_complete",
    "classification_checked",
    "releasability_checked",
    "acg_assignment_checked",
    "format_correct",
    "handling_caveats_applied",
    "manager_comments_resolved",
)


def checklist_items(answers: dict[str, bool]) -> tuple[QcChecklistItem, ...]:
    return tuple(
        QcChecklistItem(key=key, passed=answers.get(key, False)) for key in QC_CHECKLIST_KEYS
    )


def qc_decision(
    ticket_id: UUID,
    status: QcDecisionStatus,
    reason: str,
    reviewer_user_id: UUID,
    checklist: tuple[QcChecklistItem, ...],
) -> QcDecision:
    return QcDecision(
        decision_id=uuid4(),
        ticket_id=ticket_id,
        status=status,
        reason=reason,
        reviewer_user_id=reviewer_user_id,
        checklist=checklist,
        created_at=datetime.now(UTC),
    )


def queued_index(ticket_id: UUID, product_id: UUID) -> ProductIndexRecord:
    return ProductIndexRecord(
        index_id=uuid4(),
        ticket_id=ticket_id,
        product_id=product_id,
        status=ProductIndexStatus.QUEUED,
        summary="Embedding and search indexing queued.",
        created_at=datetime.now(UTC),
    )


def indexed_product(ticket_id: UUID, product_id: UUID) -> ProductIndexRecord:
    return ProductIndexRecord(
        index_id=uuid4(),
        ticket_id=ticket_id,
        product_id=product_id,
        status=ProductIndexStatus.INDEXED,
        summary="Search index updated by the local asynchronous worker.",
        created_at=datetime.now(UTC),
    )


def dissemination(
    ticket_id: UUID, product_id: UUID, recipient_user_id: UUID
) -> ProductDissemination:
    return ProductDissemination(
        dissemination_id=uuid4(),
        ticket_id=ticket_id,
        product_id=product_id,
        recipient_user_id=recipient_user_id,
        created_at=datetime.now(UTC),
    )


def feedback_request(ticket_id: UUID, product_id: UUID, requester_user_id: UUID) -> FeedbackRequest:
    return FeedbackRequest(
        request_id=uuid4(),
        ticket_id=ticket_id,
        product_id=product_id,
        requester_user_id=requester_user_id,
        status=FeedbackRequestStatus.REQUESTED,
        created_at=datetime.now(UTC),
    )


def preview_kind(mime_type: str, asset_type: str) -> str:
    if mime_type.startswith("image/"):
        return "image"
    if mime_type == "application/geo+json" or asset_type == "geojson":
        return "geojson"
    if mime_type == "application/pdf" or asset_type == "pdf":
        return "pdf_metadata"
    return "text_metadata"
