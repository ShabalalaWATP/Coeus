"""HTTP contracts for single-home organisation workforce administration."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from coeus.domain.organisation import MembershipRole, MembershipState
from coeus.domain.organisation_membership import MembershipOperation
from coeus.domain.organisation_transfer import PersonnelTransferStatus


class MembershipRequestPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    operation: MembershipOperation
    membership_id: UUID = Field(validation_alias="membershipId")
    user_id: UUID = Field(validation_alias="userId")
    unit_id: UUID = Field(validation_alias="unitId")
    expected_version: int = Field(validation_alias="expectedVersion", ge=0)
    role: MembershipRole
    assignment_eligible: bool = Field(validation_alias="assignmentEligible")
    valid_from: datetime = Field(validation_alias="validFrom")
    valid_until: datetime | None = Field(default=None, validation_alias="validUntil")
    authorising_grant_id: UUID = Field(validation_alias="authorisingGrantId")
    reason: str = Field(min_length=1, max_length=500)


class MembershipSnapshotResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    unit_version: int = Field(serialization_alias="unitVersion")
    current_membership_version: int = Field(serialization_alias="currentMembershipVersion")
    active_task_legs: int = Field(serialization_alias="activeTaskLegs")
    state_digest: str = Field(serialization_alias="stateDigest")


class MembershipPreviewResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    request: MembershipRequestPayload
    snapshot: MembershipSnapshotResponse
    preview_hash: str = Field(serialization_alias="previewHash")


class WorkforceCommandEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    command_id: UUID = Field(validation_alias="commandId")
    idempotency_key: str = Field(validation_alias="idempotencyKey", min_length=1, max_length=128)
    preview_hash: str = Field(validation_alias="previewHash", pattern=r"^[0-9a-f]{64}$")


class MembershipCommandPayload(WorkforceCommandEnvelope):
    request: MembershipRequestPayload


class MembershipResultResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    membership_id: UUID = Field(serialization_alias="membershipId")
    version: int
    replayed: bool


class MembershipRecordResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    membership_id: UUID = Field(serialization_alias="membershipId")
    user_id: UUID = Field(serialization_alias="userId")
    unit_id: UUID = Field(serialization_alias="unitId")
    role: MembershipRole
    state: MembershipState
    assignment_eligible: bool = Field(serialization_alias="assignmentEligible")
    valid_from: datetime = Field(serialization_alias="validFrom")
    valid_until: datetime | None = Field(serialization_alias="validUntil")
    version: int


class MembershipListResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    memberships: list[MembershipRecordResponse]


class TransferRequestPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    source_membership_id: UUID = Field(validation_alias="sourceMembershipId")
    target_membership_id: UUID = Field(validation_alias="targetMembershipId")
    user_id: UUID = Field(validation_alias="userId")
    source_unit_id: UUID = Field(validation_alias="sourceUnitId")
    target_unit_id: UUID = Field(validation_alias="targetUnitId")
    expected_membership_version: int = Field(validation_alias="expectedMembershipVersion", ge=1)
    expected_target_unit_version: int = Field(validation_alias="expectedTargetUnitVersion", ge=1)
    target_role: MembershipRole = Field(validation_alias="targetRole")
    assignment_eligible: bool = Field(validation_alias="assignmentEligible")
    effective_at: datetime = Field(validation_alias="effectiveAt")
    source_authorising_grant_id: UUID = Field(validation_alias="sourceAuthorisingGrantId")
    target_authorising_grant_id: UUID = Field(validation_alias="targetAuthorisingGrantId")
    reason: str = Field(min_length=1, max_length=500)


class TransferImpactResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    active_task_legs: int = Field(serialization_alias="activeTaskLegs")
    reservations: int
    future_team_events: int = Field(serialization_alias="futureTeamEvents")
    named_work_items: int = Field(serialization_alias="namedWorkItems")
    state_digest: str = Field(serialization_alias="stateDigest")


class TransferPreviewResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    request: TransferRequestPayload
    impact: TransferImpactResponse
    preview_hash: str = Field(serialization_alias="previewHash")


class TransferCommandPayload(WorkforceCommandEnvelope):
    request: TransferRequestPayload


class TransferResultResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    command_id: UUID = Field(serialization_alias="commandId")
    source_membership_id: UUID = Field(serialization_alias="sourceMembershipId")
    target_membership_id: UUID = Field(serialization_alias="targetMembershipId")
    status: PersonnelTransferStatus
    source_version: int = Field(serialization_alias="sourceVersion")
    target_version: int = Field(serialization_alias="targetVersion")
    replayed: bool
    failure_code: str = Field(serialization_alias="failureCode")
