"""API contracts for human-reviewed assignment recommendations."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

CapabilityId = Annotated[str, Field(min_length=1, max_length=120)]
WorkPackageTitle = Annotated[str, Field(min_length=3, max_length=180)]


class AssignmentRecommendationPreviewRequest(BaseModel):
    effort_min_minutes: int = Field(ge=15, le=100_800, validation_alias="effortMinMinutes")
    effort_max_minutes: int = Field(ge=15, le=100_800, validation_alias="effortMaxMinutes")
    deadline: datetime
    capability_ids: list[CapabilityId] = Field(
        min_length=1, max_length=12, validation_alias="capabilityIds"
    )
    unit_id: UUID | None = Field(default=None, validation_alias="unitId")

    @field_validator("effort_min_minutes", "effort_max_minutes")
    @classmethod
    def validate_effort_increment(cls, value: int) -> int:
        if value % 15:
            raise ValueError("effort must use 15-minute increments")
        return value

    @model_validator(mode="after")
    def validate_effort_range(self) -> "AssignmentRecommendationPreviewRequest":
        if self.effort_min_minutes > self.effort_max_minutes:
            raise ValueError("minimum effort cannot exceed maximum effort")
        return self


class AssignmentRecommendationCandidateResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    unit_id: UUID = Field(serialization_alias="unitId")
    analyst_user_id: UUID = Field(serialization_alias="analystUserId")
    display_name: str = Field(serialization_alias="displayName")
    rank: int
    assignable_minutes: int = Field(serialization_alias="assignableMinutes")
    active_wip: int = Field(serialization_alias="activeWip")
    explanation_codes: list[str] = Field(serialization_alias="explanationCodes")


class AssignmentRecommendationPreviewResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    recommendation_id: UUID = Field(serialization_alias="recommendationId")
    estimate_id: UUID = Field(serialization_alias="estimateId")
    estimate_version: int = Field(serialization_alias="estimateVersion")
    hold_id: UUID = Field(serialization_alias="holdId")
    preview_hash: str = Field(serialization_alias="previewHash")
    expires_at: datetime = Field(serialization_alias="expiresAt")
    candidates: list[AssignmentRecommendationCandidateResponse]
    exclusion_counts: dict[str, int] = Field(serialization_alias="exclusionCounts")


class AssignmentRecommendationAcceptRequest(BaseModel):
    recommendation_id: UUID = Field(validation_alias="recommendationId")
    preview_hash: str = Field(min_length=64, max_length=64, validation_alias="previewHash")
    selected_unit_id: UUID = Field(validation_alias="selectedUnitId")
    selected_analyst_user_id: UUID = Field(validation_alias="selectedAnalystUserId")
    override_reason: str = Field(default="", max_length=500, validation_alias="overrideReason")
    work_packages: list[WorkPackageTitle] = Field(
        default_factory=list, max_length=8, validation_alias="workPackages"
    )

    @field_validator("override_reason")
    @classmethod
    def validate_optional_override_reason(cls, value: str) -> str:
        reason = value.strip()
        if reason and len(reason) < 10:
            raise ValueError("an override reason must contain at least 10 characters")
        return value
