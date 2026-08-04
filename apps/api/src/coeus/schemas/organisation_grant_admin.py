"""HTTP contracts for explicit organisation management grants."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from coeus.domain.organisation import ManagementAction


class ManagementGrantResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    grant_id: UUID = Field(serialization_alias="id")
    manager_user_id: UUID = Field(serialization_alias="managerUserId")
    root_unit_id: UUID = Field(serialization_alias="rootUnitId")
    action: ManagementAction
    include_descendants: bool = Field(serialization_alias="includeDescendants")
    valid_from: datetime = Field(serialization_alias="validFrom")
    valid_until: datetime | None = Field(serialization_alias="validUntil")
    revoked_at: datetime | None = Field(serialization_alias="revokedAt")
    source_grant_id: UUID | None = Field(serialization_alias="sourceGrantId")
    delegation_depth: int = Field(serialization_alias="delegationDepth")
    version: int


class ManagementGrantListResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    grants: list[ManagementGrantResponse]


class CreateManagementGrantPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    command_id: UUID = Field(validation_alias="commandId")
    grant_id: UUID = Field(validation_alias="grantId")
    idempotency_key: str = Field(validation_alias="idempotencyKey", min_length=1, max_length=128)
    manager_user_id: UUID = Field(validation_alias="managerUserId")
    root_unit_id: UUID = Field(validation_alias="rootUnitId")
    action: ManagementAction
    include_descendants: bool = Field(validation_alias="includeDescendants")
    source_grant_id: UUID = Field(validation_alias="sourceGrantId")
    expected_source_version: int = Field(validation_alias="expectedSourceVersion", ge=1)
    reason: str = Field(min_length=1, max_length=500)
    valid_until: datetime | None = Field(default=None, validation_alias="validUntil")


class RevokeManagementGrantPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    command_id: UUID = Field(validation_alias="commandId")
    idempotency_key: str = Field(validation_alias="idempotencyKey", min_length=1, max_length=128)
    expected_version: int = Field(validation_alias="expectedVersion", ge=1)
    reason: str = Field(min_length=1, max_length=500)


class ManagementGrantResultResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    grant_id: UUID = Field(serialization_alias="grantId")
    version: int
    replayed: bool
