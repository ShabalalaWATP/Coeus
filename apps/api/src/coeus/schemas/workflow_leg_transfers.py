"""HTTP contracts for reviewed cross-team workflow-leg transfers."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from coeus.domain.team_task_ownership import WorkflowLeg
from coeus.domain.workflow_leg_transfers import PackageTransferDisposition, WorkflowLegTransferState


class PackageTransferPlanPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    package_id: UUID = Field(alias="packageId")
    disposition: PackageTransferDisposition
    expected_version: int = Field(alias="expectedVersion", ge=1)
    reservation_id: UUID | None = Field(None, alias="reservationId")
    reservation_idempotency_key: str | None = Field(
        None, alias="reservationIdempotencyKey", min_length=1, max_length=128
    )
    starts_at: datetime | None = Field(None, alias="startsAt")
    ends_at: datetime | None = Field(None, alias="endsAt")
    reserved_minutes: int | None = Field(None, alias="reservedMinutes", ge=15)


class WorkflowLegTransferProposalPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    transfer_id: UUID = Field(alias="transferId")
    ticket_id: UUID = Field(alias="ticketId")
    workflow_leg: WorkflowLeg = Field(alias="workflowLeg")
    target_unit_id: UUID = Field(alias="targetUnitId")
    target_user_id: UUID = Field(alias="targetUserId")
    expected_ownership_version: int = Field(alias="expectedOwnershipVersion", ge=1)
    expected_ticket_version: int = Field(alias="expectedTicketVersion", ge=1)
    expected_ticket_source_hash: str = Field(
        alias="expectedTicketSourceHash", pattern=r"^[0-9a-f]{64}$"
    )
    authorising_grant_id: UUID = Field(alias="authorisingGrantId")
    expected_grant_version: int = Field(alias="expectedGrantVersion", ge=1)
    expires_at: datetime = Field(alias="expiresAt")
    packages: tuple[PackageTransferPlanPayload, ...] = Field(min_length=1, max_length=64)
    reason: str = Field(min_length=1, max_length=500)


class ProposeWorkflowLegTransferPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    command_id: UUID = Field(alias="commandId")
    idempotency_key: str = Field(alias="idempotencyKey", min_length=1, max_length=128)
    proposal: WorkflowLegTransferProposalPayload
    preview_hash: str = Field(alias="previewHash", pattern=r"^[0-9a-f]{64}$")


class WorkflowLegTransferCommandPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    command_id: UUID = Field(alias="commandId")
    idempotency_key: str = Field(alias="idempotencyKey", min_length=1, max_length=128)
    expected_transfer_version: int = Field(alias="expectedTransferVersion", ge=1)
    action: str = Field(pattern=r"^(accept|reject|cancel|expire)$")
    preview_hash: str | None = Field(None, alias="previewHash", pattern=r"^[0-9a-f]{64}$")
    grant_id: UUID | None = Field(None, alias="grantId")
    expected_grant_version: int | None = Field(None, alias="expectedGrantVersion", ge=1)
    target_membership_id: UUID | None = Field(None, alias="targetMembershipId")
    expected_target_membership_version: int | None = Field(
        None, alias="expectedTargetMembershipVersion", ge=1
    )
    expected_target_account_credential_version: int | None = Field(
        None, alias="expectedTargetAccountCredentialVersion", ge=0
    )
    expected_target_account_source_hash: str | None = Field(
        None, alias="expectedTargetAccountSourceHash", pattern=r"^[0-9a-f]{64}$"
    )
    assignment_grant_id: UUID | None = Field(None, alias="assignmentGrantId")
    expected_assignment_grant_version: int | None = Field(
        None, alias="expectedAssignmentGrantVersion", ge=1
    )
    reason: str = Field(default="", max_length=500)


class WorkflowLegTransferPreviewResponse(BaseModel):
    model_config = ConfigDict(frozen=True)
    preview_hash: str = Field(serialization_alias="previewHash")
    transfer_id: UUID = Field(serialization_alias="transferId")
    ticket_id: UUID = Field(serialization_alias="ticketId")
    source_unit_id: UUID = Field(serialization_alias="sourceUnitId")
    target_unit_id: UUID = Field(serialization_alias="targetUnitId")
    package_count: int = Field(serialization_alias="packageCount")
    transfer_count: int = Field(serialization_alias="transferCount")
    expires_at: datetime = Field(serialization_alias="expiresAt")


class WorkflowLegTransferResultResponse(BaseModel):
    model_config = ConfigDict(frozen=True)
    transfer_id: UUID = Field(serialization_alias="transferId")
    state: WorkflowLegTransferState
    version: int
    replayed: bool
