"""HTTP schemas for the local-only synthetic organisation fixture."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, SecretStr


class SyntheticFixtureCountsResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    units: int
    delivery_profiles: int = Field(serialization_alias="deliveryProfiles")
    memberships: int
    working_patterns: int = Field(serialization_alias="workingPatterns")
    grants: int
    team_capabilities: int = Field(serialization_alias="teamCapabilities")
    competencies: int
    calendar_events: int = Field(serialization_alias="calendarEvents")
    tasks: int
    task_ownership: int = Field(serialization_alias="taskOwnership")
    work_packages: int = Field(serialization_alias="workPackages")
    capacity_reservations: int = Field(serialization_alias="capacityReservations")
    total: int


class SyntheticFixtureFindingResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    code: str
    entity_type: str = Field(serialization_alias="entityType")
    entity_key: str = Field(serialization_alias="entityKey")
    message: str


class SyntheticFixturePreviewResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    manifest_version: str = Field(serialization_alias="manifestVersion")
    preview_hash: str = Field(serialization_alias="previewHash")
    can_apply: bool = Field(serialization_alias="canApply")
    creates: SyntheticFixtureCountsResponse
    unchanged: SyntheticFixtureCountsResponse
    findings: list[SyntheticFixtureFindingResponse]


class SyntheticFixtureCommandRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    command_id: UUID = Field(validation_alias="commandId")
    idempotency_key: str = Field(validation_alias="idempotencyKey", min_length=1, max_length=128)
    preview_hash: str = Field(validation_alias="previewHash", pattern=r"^[0-9a-f]{64}$")
    current_password: SecretStr = Field(validation_alias="currentPassword")


class SyntheticFixtureResultResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    command_id: UUID = Field(serialization_alias="commandId")
    manifest_version: str = Field(serialization_alias="manifestVersion")
    created: SyntheticFixtureCountsResponse
    replayed: bool
    reconciled_rows: int = Field(serialization_alias="reconciledRows")
