"""HTTP contracts for organisation reparenting and deactivation."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ReparentRequestPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    unit_id: UUID = Field(validation_alias="unitId")
    new_parent_unit_id: UUID = Field(validation_alias="newParentId")
    expected_unit_version: int = Field(validation_alias="expectedUnitVersion", ge=1)
    expected_parent_version: int = Field(validation_alias="expectedParentVersion", ge=1)
    authorising_grant_id: UUID = Field(validation_alias="authorisingGrantId")
    reason: str = Field(min_length=1, max_length=500)


class ReparentImpactResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    source_parent_unit_id: UUID = Field(serialization_alias="sourceParentId")
    source_topology_revision_id: UUID = Field(serialization_alias="sourceTopologyRevisionId")
    descendants: int
    memberships: int
    grants: int
    capability_mappings: int = Field(serialization_alias="capabilityMappings")
    active_task_legs: int = Field(serialization_alias="activeTaskLegs")
    reservations: int
    team_calendar_events: int = Field(serialization_alias="teamCalendarEvents")
    pending_transfers: int = Field(serialization_alias="pendingTransfers")
    saved_views: int = Field(serialization_alias="savedViews")
    newly_covering_grants: int = Field(serialization_alias="newlyCoveringGrants")
    maximum_result_depth: int = Field(serialization_alias="maximumResultDepth")
    state_digest: str = Field(serialization_alias="stateDigest")


class ReparentPreviewResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    unit_id: UUID = Field(serialization_alias="unitId")
    new_parent_unit_id: UUID = Field(serialization_alias="newParentId")
    impact: ReparentImpactResponse
    preview_hash: str = Field(serialization_alias="previewHash")


class StructureCommandEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    command_id: UUID = Field(validation_alias="commandId")
    idempotency_key: str = Field(validation_alias="idempotencyKey", min_length=1, max_length=128)
    preview_hash: str = Field(validation_alias="previewHash", pattern=r"^[0-9a-f]{64}$")


class ReparentCommandPayload(StructureCommandEnvelope):
    request: ReparentRequestPayload


class ReparentResultResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    unit_id: UUID = Field(serialization_alias="unitId")
    parent_unit_id: UUID = Field(serialization_alias="parentId")
    version: int
    topology_revision_id: UUID = Field(serialization_alias="topologyRevisionId")
    replayed: bool


class DeactivationRequestPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    unit_id: UUID = Field(validation_alias="unitId")
    expected_version: int = Field(validation_alias="expectedVersion", ge=1)
    authorising_grant_id: UUID = Field(validation_alias="authorisingGrantId")
    reason: str = Field(min_length=1, max_length=500)


class DeactivationImpactResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    active_children: int = Field(serialization_alias="activeChildren")
    active_descendants: int = Field(serialization_alias="activeDescendants")
    memberships: int
    direct_grants: int = Field(serialization_alias="directGrants")
    delivery_profiles: int = Field(serialization_alias="deliveryProfiles")
    capability_mappings: int = Field(serialization_alias="capabilityMappings")
    active_task_legs: int = Field(serialization_alias="activeTaskLegs")
    reservations: int
    team_calendar_events: int = Field(serialization_alias="teamCalendarEvents")
    pending_transfers: int = Field(serialization_alias="pendingTransfers")
    saved_views: int = Field(serialization_alias="savedViews")
    state_digest: str = Field(serialization_alias="stateDigest")
    blocking_count: int = Field(serialization_alias="blockingCount")


class DeactivationPreviewResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    request: DeactivationRequestPayload
    impact: DeactivationImpactResponse
    preview_hash: str = Field(serialization_alias="previewHash")


class DeactivationCommandPayload(StructureCommandEnvelope):
    request: DeactivationRequestPayload


class DeactivationResultResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    unit_id: UUID = Field(serialization_alias="unitId")
    version: int
    replayed: bool
