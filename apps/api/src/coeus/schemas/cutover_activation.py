"""Public-safe contracts for the exact-candidate cutover ceremony."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, SecretStr

from coeus.domain.cutover_activation import (
    CutoverApprovalRole,
    CutoverSlice,
    CutoverSliceStatus,
)

_HASH = r"^[0-9a-f]{64}$"
_REFERENCE = r"^[A-Za-z0-9][A-Za-z0-9._:/@+-]{0,127}$"


class CutoverManifestPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    source_revision: str = Field(validation_alias="sourceRevision", pattern=_REFERENCE)
    schema_head: str = Field(validation_alias="schemaHead", pattern=_REFERENCE)
    organisation_parity_hash: str = Field(validation_alias="organisationParityHash", pattern=_HASH)
    calendar_parity_hash: str = Field(validation_alias="calendarParityHash", pattern=_HASH)
    task_capacity_parity_hash: str = Field(validation_alias="taskCapacityParityHash", pattern=_HASH)
    routing_evaluation_release: str = Field(
        validation_alias="routingEvaluationRelease", pattern=_REFERENCE
    )
    routing_evaluation_hash: str = Field(validation_alias="routingEvaluationHash", pattern=_HASH)
    protected_checks_reference: str = Field(
        validation_alias="protectedChecksReference", pattern=_REFERENCE
    )
    protected_checks_hash: str = Field(validation_alias="protectedChecksHash", pattern=_HASH)
    browser_evidence_hash: str = Field(validation_alias="browserEvidenceHash", pattern=_HASH)
    security_review_reference: str = Field(
        validation_alias="securityReviewReference", pattern=_REFERENCE
    )
    security_review_hash: str = Field(validation_alias="securityReviewHash", pattern=_HASH)
    backup_restore_hash: str = Field(validation_alias="backupRestoreHash", pattern=_HASH)


class CutoverApprovalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slice: CutoverSlice
    candidate_hash: str = Field(validation_alias="candidateDigest", pattern=_HASH)
    preview_hash: str = Field(validation_alias="previewDigest", pattern=_HASH)
    approval_role: CutoverApprovalRole = Field(validation_alias="approvalRole")
    current_password: SecretStr = Field(validation_alias="currentPassword", min_length=1)


class CutoverExecutionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_hash: str = Field(validation_alias="candidateDigest", pattern=_HASH)
    approval_ids: tuple[UUID, UUID] = Field(validation_alias="approvalIds")
    current_password: SecretStr = Field(validation_alias="currentPassword", min_length=1)


class CutoverManifestResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    source_revision: str = Field(serialization_alias="sourceRevision")
    schema_head: str = Field(serialization_alias="schemaHead")
    organisation_parity_hash: str = Field(serialization_alias="organisationParityHash")
    calendar_parity_hash: str = Field(serialization_alias="calendarParityHash")
    task_capacity_parity_hash: str = Field(serialization_alias="taskCapacityParityHash")
    routing_evaluation_release: str = Field(serialization_alias="routingEvaluationRelease")
    routing_evaluation_hash: str = Field(serialization_alias="routingEvaluationHash")
    protected_checks_reference: str = Field(serialization_alias="protectedChecksReference")
    protected_checks_hash: str = Field(serialization_alias="protectedChecksHash")
    browser_evidence_hash: str = Field(serialization_alias="browserEvidenceHash")
    security_review_reference: str = Field(serialization_alias="securityReviewReference")
    security_review_hash: str = Field(serialization_alias="securityReviewHash")
    backup_restore_hash: str = Field(serialization_alias="backupRestoreHash")


class CutoverSlicePreviewResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    slice: CutoverSlice
    candidate_hash: str = Field(serialization_alias="candidateDigest")
    preview_hash: str = Field(serialization_alias="previewDigest")
    proposed_by_user_id: UUID = Field(serialization_alias="proposedByUserId")
    expires_at: datetime = Field(serialization_alias="expiresAt")


class CutoverSliceApprovalResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    approval_id: UUID = Field(serialization_alias="approvalId")
    slice: CutoverSlice
    candidate_hash: str = Field(serialization_alias="candidateDigest")
    preview_hash: str = Field(serialization_alias="previewDigest")
    approval_role: CutoverApprovalRole = Field(serialization_alias="approvalRole")
    approved_by_user_id: UUID = Field(serialization_alias="approvedByUserId")
    approved_at: datetime = Field(serialization_alias="approvedAt")


class CutoverSliceStateResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    slice: CutoverSlice
    status: CutoverSliceStatus
    preview_hash: str | None = Field(default=None, serialization_alias="previewDigest")
    proposed_by_user_id: UUID | None = Field(default=None, serialization_alias="proposedByUserId")
    approvals: list[CutoverSliceApprovalResponse]
    activated_by_user_id: UUID | None = Field(default=None, serialization_alias="activatedByUserId")
    activated_at: datetime | None = Field(default=None, serialization_alias="activatedAt")


class CutoverReleaseStateResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    candidate_hash: str | None = Field(serialization_alias="candidateDigest")
    manifest: CutoverManifestResponse | None
    slices: list[CutoverSliceStateResponse]
    eligible: bool


class CutoverExecutionResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    candidate_hash: str = Field(serialization_alias="candidateDigest")
    slice: CutoverSlice
    status: CutoverSliceStatus
    eligible: bool
