from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from coeus.schemas.routing import PriorityAssessmentResponse


class QcApprovalRequest(BaseModel):
    checklist: dict[str, bool]
    classification_level: int = Field(ge=0, le=5, validation_alias="classificationLevel")
    releasability: list[str] = Field(min_length=1, max_length=12)
    handling_caveats: list[str] = Field(
        min_length=1, max_length=12, validation_alias="handlingCaveats"
    )
    acg_ids: list[UUID] = Field(min_length=1, max_length=12, validation_alias="acgIds")
    reason: str = Field(min_length=3, max_length=1_000)


class QcRejectRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=1_000)


class QcChecklistItemResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    key: str
    passed: bool


class QcDraftAssetResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    asset_id: UUID = Field(serialization_alias="id")
    name: str
    asset_type: str = Field(serialization_alias="assetType")
    mime_type: str = Field(serialization_alias="mimeType")
    size_bytes: int = Field(serialization_alias="sizeBytes")
    sha256: str
    detected_mime_type: str = Field(serialization_alias="detectedMimeType")
    preview_kind: str = Field(serialization_alias="previewKind")
    processing_status: str = Field(serialization_alias="processingStatus")
    preview_available: bool = Field(serialization_alias="previewAvailable")


class QcDraftResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    version_id: UUID = Field(serialization_alias="id")
    version_number: int = Field(serialization_alias="versionNumber")
    title: str
    summary: str
    product_type: str = Field(serialization_alias="productType")
    content: str
    description: str
    manifest_hash: str = Field(serialization_alias="manifestHash")
    created_by_user_id: UUID = Field(serialization_alias="createdByUserId")
    created_at: datetime = Field(serialization_alias="createdAt")
    assets: list[QcDraftAssetResponse]


class QcDecisionResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    decision_id: UUID = Field(serialization_alias="id")
    status: str
    reason: str
    reviewer_user_id: UUID = Field(serialization_alias="reviewerUserId")
    checklist: list[QcChecklistItemResponse]
    created_at: datetime = Field(serialization_alias="createdAt")


class QcAgentCheckResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    key: str
    passed: bool
    detail: str


class QcAgentFindingResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    finding_id: UUID = Field(serialization_alias="id")
    category: str
    severity: str
    original_text: str = Field(serialization_alias="originalText")
    suggested_text: str = Field(serialization_alias="suggestedText")
    location: str
    detail: str
    confidence: float
    blocking: bool


class QcAgentPreflightResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    preflight_id: UUID = Field(serialization_alias="id")
    draft_version_id: UUID = Field(serialization_alias="draftVersionId")
    status: str
    checks: list[QcAgentCheckResponse]
    blockers: list[str]
    policy_version: str = Field(serialization_alias="policyVersion")
    created_at: datetime = Field(serialization_alias="createdAt")
    findings: list[QcAgentFindingResponse]


class QcIndexRecordResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    index_id: UUID = Field(serialization_alias="id")
    product_id: UUID = Field(serialization_alias="productId")
    status: str
    summary: str
    created_at: datetime = Field(serialization_alias="createdAt")


class QcDisseminationResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    dissemination_id: UUID = Field(serialization_alias="id")
    product_id: UUID = Field(serialization_alias="productId")
    recipient_user_id: UUID = Field(serialization_alias="recipientUserId")
    created_at: datetime = Field(serialization_alias="createdAt")


class QcFeedbackRequestResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    request_id: UUID = Field(serialization_alias="id")
    product_id: UUID = Field(serialization_alias="productId")
    requester_user_id: UUID = Field(serialization_alias="requesterUserId")
    status: str
    created_at: datetime = Field(serialization_alias="createdAt")


class QcProductSummaryResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    product_id: UUID = Field(serialization_alias="id")
    reference: str
    title: str
    status: str
    acg_ids: list[UUID] = Field(serialization_alias="acgIds")


class QcProductResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    ticket_id: UUID = Field(serialization_alias="ticketId")
    reference: str
    requester_user_id: UUID = Field(serialization_alias="requesterUserId")
    state: str
    title: str
    operational_question: str | None = Field(serialization_alias="operationalQuestion")
    area_or_region: str | None = Field(serialization_alias="areaOrRegion")
    priority: str | None
    priority_assessment: PriorityAssessmentResponse = Field(
        serialization_alias="priorityAssessment"
    )
    required_output_format: str | None = Field(serialization_alias="requiredOutputFormat")
    checklist_keys: list[str] = Field(serialization_alias="checklistKeys")
    latest_draft: QcDraftResponse | None = Field(serialization_alias="latestDraft")
    manager_notes: list[str] = Field(serialization_alias="managerNotes")
    decisions: list[QcDecisionResponse]
    agent_preflight: QcAgentPreflightResponse | None = Field(serialization_alias="agentPreflight")
    index_records: list[QcIndexRecordResponse] = Field(serialization_alias="indexRecords")
    disseminations: list[QcDisseminationResponse]
    feedback_requests: list[QcFeedbackRequestResponse] = Field(
        serialization_alias="feedbackRequests"
    )
    ingested_product: QcProductSummaryResponse | None = Field(serialization_alias="ingestedProduct")


class QcQueueItemResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    ticket_id: UUID = Field(serialization_alias="ticketId")
    reference: str
    state: str
    claim_status: str = Field(serialization_alias="claimStatus")


class QcQueueResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    products: list[QcProductResponse]
    items: list[QcQueueItemResponse] = Field(default_factory=list)
