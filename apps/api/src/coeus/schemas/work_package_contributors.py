"""HTTP contracts for reviewed contributor lifecycle changes."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from coeus.domain.work_package_contributors import ContributorOperation


class ContributorCapacityPlanPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    reservation_id: UUID = Field(alias="reservationId")
    starts_at: datetime = Field(alias="startsAt")
    ends_at: datetime = Field(alias="endsAt")
    reserved_minutes: int = Field(alias="reservedMinutes", gt=0, multiple_of=15)
    idempotency_key: str = Field(alias="idempotencyKey", min_length=1, max_length=128)


class ContributorChangePayload(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    contributor_user_id: UUID = Field(alias="contributorUserId")
    operation: ContributorOperation
    expected_package_version: int = Field(alias="expectedPackageVersion", ge=1)
    expected_ownership_version: int = Field(alias="expectedOwnershipVersion", ge=1)
    authorising_grant_id: UUID = Field(alias="authorisingGrantId")
    expected_grant_version: int = Field(alias="expectedGrantVersion", ge=1)
    membership_id: UUID = Field(alias="membershipId")
    expected_membership_version: int = Field(alias="expectedMembershipVersion", ge=1)
    expected_account_credential_version: int = Field(alias="expectedAccountCredentialVersion", ge=0)
    expected_account_source_hash: str = Field(
        alias="expectedAccountSourceHash", pattern=r"^[0-9a-f]{64}$"
    )
    capacity_plan: ContributorCapacityPlanPayload | None = Field(default=None, alias="capacityPlan")


class ContributorChangePreviewResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    preview_hash: str = Field(serialization_alias="previewHash")
    package_id: UUID = Field(serialization_alias="packageId")
    package_version: int = Field(serialization_alias="packageVersion")
    ownership_version: int = Field(serialization_alias="ownershipVersion")
    contributor_user_id: UUID = Field(serialization_alias="contributorUserId")
    contributor_active: bool = Field(serialization_alias="contributorActive")
    planned_package_version: int = Field(serialization_alias="plannedPackageVersion")


class ChangeContributorCommandPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    command_id: UUID = Field(alias="commandId")
    idempotency_key: str = Field(alias="idempotencyKey", min_length=1, max_length=128)
    request: ContributorChangePayload
    preview_hash: str = Field(alias="previewHash", pattern=r"^[0-9a-f]{64}$")


class ContributorChangeResultResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    package_id: UUID = Field(serialization_alias="packageId")
    package_version: int = Field(serialization_alias="packageVersion")
    contributor_user_id: UUID = Field(serialization_alias="contributorUserId")
    contributor_active: bool = Field(serialization_alias="contributorActive")
    replayed: bool
