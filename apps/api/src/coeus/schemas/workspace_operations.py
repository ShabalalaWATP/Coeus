"""HTTP contracts for integrated team workspace operations."""

from datetime import datetime, time
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from coeus.domain.workspace_operations import PlanningCadence, WorkspaceScope


class MetricResponse(BaseModel):
    model_config = ConfigDict(frozen=True)
    key: str
    label: str
    value: int | None
    display: str
    scope: WorkspaceScope
    period: str
    suppressed: bool


class OverviewResponse(BaseModel):
    model_config = ConfigDict(frozen=True)
    unit_id: UUID = Field(serialization_alias="unitId")
    scope: WorkspaceScope
    generated_at: datetime = Field(serialization_alias="generatedAt")
    fresh_until: datetime = Field(serialization_alias="freshUntil")
    metrics: list[MetricResponse]
    descendant_units: int = Field(serialization_alias="descendantUnits")
    suppressed: bool


class PersonResponse(BaseModel):
    model_config = ConfigDict(frozen=True)
    user_id: UUID = Field(serialization_alias="userId")
    display_name: str = Field(serialization_alias="displayName")
    membership_role: str = Field(serialization_alias="membershipRole")
    assignment_eligible: bool = Field(serialization_alias="assignmentEligible")
    working_pattern: str = Field(serialization_alias="workingPattern")


class PeopleResponse(BaseModel):
    model_config = ConfigDict(frozen=True)
    items: list[PersonResponse]
    truncated: bool


class CapabilityResponse(BaseModel):
    model_config = ConfigDict(frozen=True)
    capability_id: str = Field(serialization_alias="capabilityId")
    required_proficiency: int = Field(serialization_alias="requiredProficiency")
    verified_people: int | None = Field(serialization_alias="verifiedPeople")
    display: str
    gap: bool | None
    suppressed: bool


class CapabilitiesResponse(BaseModel):
    model_config = ConfigDict(frozen=True)
    items: list[CapabilityResponse]


class PolicyResponse(BaseModel):
    model_config = ConfigDict(frozen=True)
    unit_id: UUID = Field(serialization_alias="unitId")
    wip_limit: int = Field(serialization_alias="wipLimit")
    service_target_hours: int = Field(serialization_alias="serviceTargetHours")
    planning_cadence: PlanningCadence = Field(serialization_alias="planningCadence")
    planning_weekday: int = Field(serialization_alias="planningWeekday")
    planning_local_time: time = Field(serialization_alias="planningLocalTime")
    planning_duration_minutes: int = Field(serialization_alias="planningDurationMinutes")
    version: int
    delivery_policy_version: int = Field(serialization_alias="deliveryPolicyVersion")
    updated_at: datetime = Field(serialization_alias="updatedAt")


class SavePolicyRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    command_id: UUID = Field(alias="commandId")
    idempotency_key: str = Field(alias="idempotencyKey", min_length=1, max_length=128)
    authorising_grant_id: UUID = Field(alias="authorisingGrantId")
    expected_grant_version: int = Field(alias="expectedGrantVersion", ge=1)
    expected_version: int = Field(alias="expectedVersion", ge=0)
    expected_delivery_policy_version: int = Field(alias="expectedDeliveryPolicyVersion", ge=1)
    wip_limit: int = Field(alias="wipLimit", ge=1, le=500)
    service_target_hours: int = Field(alias="serviceTargetHours", ge=1, le=8760)
    planning_cadence: PlanningCadence = Field(alias="planningCadence")
    planning_weekday: int = Field(alias="planningWeekday", ge=0, le=6)
    planning_local_time: time = Field(alias="planningLocalTime")
    planning_duration_minutes: int = Field(alias="planningDurationMinutes", ge=15, le=480)

    @field_validator("planning_duration_minutes")
    @classmethod
    def quarter_hour_duration(cls, value: int) -> int:
        if value % 15:
            raise ValueError("planning duration must use 15-minute increments")
        return value


class SearchResultResponse(BaseModel):
    model_config = ConfigDict(frozen=True)
    result_type: str = Field(serialization_alias="resultType")
    object_id: UUID = Field(serialization_alias="objectId")
    unit_id: UUID = Field(serialization_alias="unitId")
    label: str
    context: str


class SearchResponse(BaseModel):
    model_config = ConfigDict(frozen=True)
    items: list[SearchResultResponse]
    truncated: bool
    next_cursor: int | None = Field(serialization_alias="nextCursor")


class AnalyticsResponse(BaseModel):
    model_config = ConfigDict(frozen=True)
    unit_id: UUID = Field(serialization_alias="unitId")
    scope: WorkspaceScope
    generated_at: datetime = Field(serialization_alias="generatedAt")
    metrics: list[MetricResponse]
    privacy_notice: str = Field(serialization_alias="privacyNotice")


class CreateExportRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    command_id: UUID = Field(alias="commandId")
    idempotency_key: str = Field(alias="idempotencyKey", min_length=1, max_length=128)
    export_id: UUID = Field(alias="exportId")
    include_descendants: bool = Field(alias="includeDescendants")
    authorising_grant_id: UUID = Field(alias="authorisingGrantId")
    expected_grant_version: int = Field(alias="expectedGrantVersion", ge=1)
    format: Literal["csv"] = "csv"


class ExportResponse(BaseModel):
    model_config = ConfigDict(frozen=True)
    export_id: UUID = Field(serialization_alias="exportId")
    unit_id: UUID = Field(serialization_alias="unitId")
    state: str
    row_count: int = Field(serialization_alias="rowCount")
    created_at: datetime = Field(serialization_alias="createdAt")
    expires_at: datetime = Field(serialization_alias="expiresAt")
