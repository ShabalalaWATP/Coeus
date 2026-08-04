"""HTTP contracts for management-only organisation administration."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, SecretStr

from coeus.domain.organisation import OrganisationCategory
from coeus.domain.organisation_lifecycle import OrganisationMutationOperation


class OrganisationUnitResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    unit_id: UUID = Field(serialization_alias="id")
    name: str
    short_name: str = Field(serialization_alias="shortName")
    category: OrganisationCategory
    parent_unit_id: UUID | None = Field(serialization_alias="parentId")
    is_active: bool = Field(serialization_alias="isActive")
    valid_from: datetime = Field(serialization_alias="validFrom")
    valid_until: datetime | None = Field(serialization_alias="validUntil")
    time_zone: str = Field(serialization_alias="timeZone")
    description: str
    version: int


class OrganisationUnitListResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    units: list[OrganisationUnitResponse]


class OrganisationMutationPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: OrganisationMutationOperation
    unit_id: UUID = Field(validation_alias="unitId")
    parent_unit_id: UUID | None = Field(default=None, validation_alias="parentId")
    expected_version: int = Field(validation_alias="expectedVersion", ge=1)
    name: str = Field(min_length=1, max_length=120)
    short_name: str = Field(validation_alias="shortName", min_length=1, max_length=32)
    category: OrganisationCategory
    time_zone: str = Field(validation_alias="timeZone", min_length=1, max_length=64)
    description: str = Field(default="", max_length=1_000)
    authorising_grant_id: UUID = Field(validation_alias="authorisingGrantId")
    reason: str = Field(min_length=1, max_length=500)


class OrganisationMutationPreviewResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    operation: OrganisationMutationOperation
    unit_id: UUID = Field(serialization_alias="unitId")
    scope_unit_id: UUID = Field(serialization_alias="scopeUnitId")
    expected_version: int = Field(serialization_alias="expectedVersion")
    preview_hash: str = Field(serialization_alias="previewHash")
    affected_descendants: int = Field(serialization_alias="affectedDescendants")
    affected_memberships: int = Field(serialization_alias="affectedMemberships")
    affected_grants: int = Field(serialization_alias="affectedGrants")
    affected_task_legs: int = Field(serialization_alias="affectedTaskLegs")


class OrganisationMutationCommandRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    command_id: UUID = Field(validation_alias="commandId")
    idempotency_key: str = Field(validation_alias="idempotencyKey", min_length=1, max_length=128)
    preview_hash: str = Field(validation_alias="previewHash", pattern=r"^[0-9a-f]{64}$")
    request: OrganisationMutationPayload


class OrganisationMutationResultResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    unit_id: UUID = Field(serialization_alias="unitId")
    version: int
    topology_revision_id: UUID | None = Field(serialization_alias="topologyRevisionId")
    replayed: bool


class OrganisationBootstrapRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    command_id: UUID = Field(validation_alias="commandId")
    root_unit_id: UUID = Field(validation_alias="rootUnitId")
    root_name: str = Field(validation_alias="rootName", min_length=1, max_length=120)
    root_short_name: str = Field(validation_alias="rootShortName", min_length=1, max_length=32)
    time_zone: str = Field(validation_alias="timeZone", min_length=1, max_length=64)
    description: str = Field(default="", max_length=1_000)
    current_password: SecretStr = Field(validation_alias="currentPassword")
    setup_nonce: SecretStr = Field(validation_alias="setupNonce")


class OrganisationBootstrapResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    root_unit_id: UUID = Field(serialization_alias="rootUnitId")
    topology_revision_id: UUID = Field(serialization_alias="topologyRevisionId")
    grant_ids: tuple[UUID, ...] = Field(serialization_alias="grantIds")
