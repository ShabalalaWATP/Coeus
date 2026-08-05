"""HTTP contracts for atomic work-package planning and capacity reservation."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class WorkPackagePlanPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    expected_package_version: int = Field(alias="expectedPackageVersion", ge=1)
    expected_ownership_version: int = Field(alias="expectedOwnershipVersion", ge=1)
    accountable_user_id: UUID = Field(alias="accountableUserId")
    estimated_minutes: int = Field(alias="estimatedMinutes", ge=15, multiple_of=15)
    remaining_minutes: int = Field(alias="remainingMinutes", ge=0, multiple_of=15)
    due_at: datetime = Field(alias="dueAt")
    priority: int = Field(ge=1, le=5)
    priority_override_reason: str = Field(
        default="", alias="priorityOverrideReason", max_length=500
    )
    reservation_id: UUID = Field(alias="reservationId")
    starts_at: datetime = Field(alias="startsAt")
    ends_at: datetime = Field(alias="endsAt")
    reserved_minutes: int = Field(alias="reservedMinutes", ge=15, multiple_of=15)
    authorising_grant_id: UUID = Field(alias="authorisingGrantId")


class WorkPackagePlanningPreviewResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    preview_hash: str = Field(serialization_alias="previewHash")
    package_id: UUID = Field(serialization_alias="packageId")
    package_version: int = Field(serialization_alias="packageVersion")
    ownership_version: int = Field(serialization_alias="ownershipVersion")
    accountable_user_id: UUID = Field(serialization_alias="accountableUserId")
    planned_package_version: int = Field(serialization_alias="plannedPackageVersion")


class PlanWorkPackageCommandPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    command_id: UUID = Field(alias="commandId")
    idempotency_key: str = Field(alias="idempotencyKey", min_length=1, max_length=128)
    request: WorkPackagePlanPayload
    preview_hash: str = Field(alias="previewHash", pattern=r"^[0-9a-f]{64}$")


class CapacityReservationResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    reservation_id: UUID = Field(serialization_alias="reservationId")
    user_id: UUID = Field(serialization_alias="userId")
    package_id: UUID = Field(serialization_alias="packageId")
    starts_at: datetime = Field(serialization_alias="startsAt")
    ends_at: datetime = Field(serialization_alias="endsAt")
    reserved_minutes: int = Field(serialization_alias="reservedMinutes")
    state: str
    version: int


class WorkPackagePlanningResultResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    package_id: UUID = Field(serialization_alias="packageId")
    package_version: int = Field(serialization_alias="packageVersion")
    reservation: CapacityReservationResponse
    replayed: bool
