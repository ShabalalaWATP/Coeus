"""HTTP contracts for explicit-disposition organisation splits."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from coeus.domain.organisation import OrganisationCategory
from coeus.schemas.organisation_merge_admin import (
    AffectedRecordResponse,
    DispositionPayload,
    UnitVersionPayload,
)


class SplitSuccessorPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    unit_id: UUID = Field(validation_alias="unitId", serialization_alias="unitId")
    name: str = Field(min_length=1, max_length=120)
    short_name: str = Field(
        validation_alias="shortName", serialization_alias="shortName", min_length=1, max_length=32
    )
    category: OrganisationCategory
    time_zone: str = Field(
        validation_alias="timeZone", serialization_alias="timeZone", min_length=1, max_length=64
    )
    description: str = Field(default="", max_length=1_000)


class SplitRequestPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    source: UnitVersionPayload
    parent: UnitVersionPayload
    successors: list[SplitSuccessorPayload] = Field(min_length=2, max_length=100)
    source_authorising_grant_id: UUID = Field(
        validation_alias="sourceAuthorisingGrantId",
        serialization_alias="sourceAuthorisingGrantId",
    )
    parent_authorising_grant_id: UUID = Field(
        validation_alias="parentAuthorisingGrantId",
        serialization_alias="parentAuthorisingGrantId",
    )
    reason: str = Field(min_length=1, max_length=500)


class SplitImpactResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    records: list[AffectedRecordResponse]
    reservations: int
    team_calendar_events: int = Field(serialization_alias="teamCalendarEvents")
    saved_views: int = Field(serialization_alias="savedViews")
    state_digest: str = Field(serialization_alias="stateDigest")


class SplitPlanPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    request: SplitRequestPayload
    dispositions: list[DispositionPayload] = Field(max_length=10_000)


class SplitPreviewResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    impact: SplitImpactResponse
    preview_hash: str = Field(serialization_alias="previewHash")


class SplitCommandPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    command_id: UUID = Field(validation_alias="commandId")
    idempotency_key: str = Field(validation_alias="idempotencyKey", min_length=1, max_length=128)
    preview_hash: str = Field(validation_alias="previewHash", pattern=r"^[0-9a-f]{64}$")
    plan: SplitPlanPayload


class SplitResultResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    source: UnitVersionPayload
    parent: UnitVersionPayload
    successors: list[UnitVersionPayload]
    replayed: bool
