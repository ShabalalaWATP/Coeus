"""HTTP contracts for accountable-owner handover."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from coeus.domain.work_package_handovers import ReservationDisposition


class ReservationHandoverPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    source_reservation_id: UUID = Field(alias="sourceReservationId")
    expected_source_version: int = Field(alias="expectedSourceVersion", ge=1)
    disposition: ReservationDisposition
    replacement_reservation_id: UUID | None = Field(default=None, alias="replacementReservationId")
    replacement_idempotency_key: str | None = Field(
        default=None, alias="replacementIdempotencyKey", min_length=1, max_length=128
    )

    @model_validator(mode="after")
    def validate_replacement(self) -> "ReservationHandoverPayload":
        replacement = self.disposition is ReservationDisposition.REPLACE
        if replacement != (self.replacement_reservation_id is not None) or replacement != (
            self.replacement_idempotency_key is not None
        ):
            raise ValueError("replacement evidence must match its disposition")
        return self


class WorkPackageHandoverPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    target_user_id: UUID = Field(alias="targetUserId")
    expected_package_version: int = Field(alias="expectedPackageVersion", ge=1)
    expected_ownership_version: int = Field(alias="expectedOwnershipVersion", ge=1)
    authorising_grant_id: UUID = Field(alias="authorisingGrantId")
    expected_grant_version: int = Field(alias="expectedGrantVersion", ge=1)
    target_membership_id: UUID = Field(alias="targetMembershipId")
    expected_target_membership_version: int = Field(alias="expectedTargetMembershipVersion", ge=1)
    expected_target_account_credential_version: int = Field(
        alias="expectedTargetAccountCredentialVersion", ge=0
    )
    expected_target_account_source_hash: str = Field(
        alias="expectedTargetAccountSourceHash", pattern=r"^[0-9a-f]{64}$"
    )
    expected_ticket_version: int = Field(alias="expectedTicketVersion", ge=1)
    expected_ticket_source_hash: str = Field(
        alias="expectedTicketSourceHash", pattern=r"^[0-9a-f]{64}$"
    )
    reservations: tuple[ReservationHandoverPayload, ...] = Field(max_length=64)


class WorkPackageHandoverPreviewResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    preview_hash: str = Field(serialization_alias="previewHash")
    package_id: UUID = Field(serialization_alias="packageId")
    source_user_id: UUID = Field(serialization_alias="sourceUserId")
    target_user_id: UUID = Field(serialization_alias="targetUserId")
    package_version: int = Field(serialization_alias="packageVersion")
    planned_package_version: int = Field(serialization_alias="plannedPackageVersion")
    participant_count: int = Field(serialization_alias="participantCount")
    reservation_count: int = Field(serialization_alias="reservationCount")
    dependency_count: int = Field(serialization_alias="dependencyCount")


class HandoverWorkPackageCommandPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    command_id: UUID = Field(alias="commandId")
    idempotency_key: str = Field(alias="idempotencyKey", min_length=1, max_length=128)
    request: WorkPackageHandoverPayload
    preview_hash: str = Field(alias="previewHash", pattern=r"^[0-9a-f]{64}$")


class WorkPackageHandoverResultResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    package_id: UUID = Field(serialization_alias="packageId")
    source_user_id: UUID = Field(serialization_alias="sourceUserId")
    target_user_id: UUID = Field(serialization_alias="targetUserId")
    package_version: int = Field(serialization_alias="packageVersion")
    released_reservation_count: int = Field(serialization_alias="releasedReservationCount")
    replacement_reservation_count: int = Field(serialization_alias="replacementReservationCount")
    replayed: bool
