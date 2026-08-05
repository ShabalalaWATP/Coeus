"""HTTP contracts for explicit-disposition organisation merges."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from coeus.domain.organisation_merge import MergeDispositionAction, MergeRecordKind


class UnitVersionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    unit_id: UUID = Field(validation_alias="unitId", serialization_alias="unitId")
    expected_version: int = Field(
        validation_alias="expectedVersion", serialization_alias="expectedVersion", ge=1
    )


class UnitAuthorityPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    unit_id: UUID = Field(validation_alias="unitId", serialization_alias="unitId")
    grant_id: UUID = Field(validation_alias="grantId", serialization_alias="grantId")


class MergeRequestPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    sources: list[UnitVersionPayload] = Field(min_length=2, max_length=100)
    successor: UnitVersionPayload
    authorities: list[UnitAuthorityPayload] = Field(min_length=3, max_length=101)
    reason: str = Field(min_length=1, max_length=500)


class AffectedRecordResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: MergeRecordKind
    record_id: UUID = Field(serialization_alias="recordId")
    source_unit_id: UUID = Field(serialization_alias="sourceUnitId")
    version: int
    container_id: UUID | None = Field(serialization_alias="containerId")


class MergeImpactResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    records: list[AffectedRecordResponse]
    active_children: int = Field(serialization_alias="activeChildren")
    newly_covering_grants: int = Field(serialization_alias="newlyCoveringGrants")
    maximum_result_depth: int = Field(serialization_alias="maximumResultDepth")
    reservations: int
    team_calendar_events: int = Field(serialization_alias="teamCalendarEvents")
    saved_views: int = Field(serialization_alias="savedViews")
    successor_has_delivery_profile: bool = Field(serialization_alias="successorHasDeliveryProfile")
    state_digest: str = Field(serialization_alias="stateDigest")


class DispositionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    kind: MergeRecordKind
    record_id: UUID = Field(validation_alias="recordId", serialization_alias="recordId")
    expected_version: int = Field(
        validation_alias="expectedVersion", serialization_alias="expectedVersion", ge=1
    )
    action: MergeDispositionAction
    target_unit_id: UUID | None = Field(
        default=None, validation_alias="targetUnitId", serialization_alias="targetUnitId"
    )
    replacement_id: UUID | None = Field(
        default=None, validation_alias="replacementId", serialization_alias="replacementId"
    )


class MergePlanPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    request: MergeRequestPayload
    dispositions: list[DispositionPayload] = Field(max_length=10_000)


class MergePreviewResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    impact: MergeImpactResponse
    preview_hash: str = Field(serialization_alias="previewHash")


class MergeCommandPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    command_id: UUID = Field(validation_alias="commandId")
    idempotency_key: str = Field(validation_alias="idempotencyKey", min_length=1, max_length=128)
    preview_hash: str = Field(validation_alias="previewHash", pattern=r"^[0-9a-f]{64}$")
    plan: MergePlanPayload


class MergeResultResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    successor_unit_id: UUID = Field(serialization_alias="successorUnitId")
    successor_version: int = Field(serialization_alias="successorVersion")
    source_versions: list[UnitVersionPayload] = Field(serialization_alias="sourceVersions")
    replayed: bool
