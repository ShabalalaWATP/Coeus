from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from coeus.domain.store import normalise_synthetic_release_markers
from coeus.schemas.tickets import ChatMessageResponse

WorkPackageText = Annotated[str, Field(min_length=3, max_length=180)]


class AnalystAssignmentRequest(BaseModel):
    analyst_user_ids: list[UUID] = Field(
        min_length=1,
        max_length=5,
        validation_alias="analystUserIds",
    )
    team_id: UUID = Field(validation_alias="teamId")
    work_packages: list[WorkPackageText] = Field(
        default_factory=list,
        max_length=8,
        validation_alias="workPackages",
    )


class AnalystNoteRequest(BaseModel):
    body: str = Field(min_length=3, max_length=2_000)


class AnalystConversationResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    messages: list[ChatMessageResponse]


class LinkProductRequest(BaseModel):
    product_id: UUID = Field(validation_alias="productId")


class WorkPackageUpdateRequest(BaseModel):
    status: str = Field(pattern="^(pending|complete)$")


class DraftAssetRequest(BaseModel):
    name: str = Field(min_length=3, max_length=180)
    asset_type: str = Field(min_length=2, max_length=80, validation_alias="assetType")
    mime_type: str = Field(min_length=3, max_length=120, validation_alias="mimeType")
    size_bytes: int = Field(gt=0, validation_alias="sizeBytes")
    sha256: str = Field(min_length=64, max_length=64)


class DraftProductRequest(BaseModel):
    title: str = Field(min_length=3, max_length=180)
    summary: str = Field(min_length=3, max_length=500)
    product_type: str = Field(min_length=3, max_length=80, validation_alias="productType")
    content: str = Field(min_length=10, max_length=20_000)
    assets: list[DraftAssetRequest] = Field(default_factory=list, max_length=5)


class ProductSubmissionMetadataRequest(BaseModel):
    title: str = Field(min_length=3, max_length=180)
    summary: str = Field(min_length=3, max_length=500)
    description: str = Field(min_length=3, max_length=2_000)
    product_type: str = Field(min_length=2, max_length=80, validation_alias="productType")
    source_type: str = Field(min_length=2, max_length=80, validation_alias="sourceType")
    owner_team: str = Field(min_length=2, max_length=80, validation_alias="ownerTeam")
    area_or_region: str = Field(min_length=2, max_length=180, validation_alias="areaOrRegion")
    classification_level: int = Field(ge=0, le=5, validation_alias="classificationLevel")
    releasability: list[str] = Field(min_length=1, max_length=12)
    handling_caveats: list[str] = Field(
        min_length=1, max_length=12, validation_alias="handlingCaveats"
    )
    tags: list[str] = Field(default_factory=list, max_length=30)
    acg_ids: list[UUID] = Field(min_length=1, max_length=20, validation_alias="acgIds")
    time_period_start: str | None = Field(default=None, validation_alias="timePeriodStart")
    time_period_end: str | None = Field(default=None, validation_alias="timePeriodEnd")

    def release_markers(self) -> tuple[tuple[str, ...], tuple[str, ...]]:
        return normalise_synthetic_release_markers(self.releasability, self.handling_caveats)


class AnalystCandidateResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    user_id: UUID = Field(serialization_alias="userId")
    username: str
    display_name: str = Field(serialization_alias="displayName")


class AnalystAssignmentResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    assignment_id: UUID = Field(serialization_alias="id")
    analyst_user_id: UUID = Field(serialization_alias="analystUserId")
    assigned_by_user_id: UUID = Field(serialization_alias="assignedByUserId")
    route: str
    created_at: datetime = Field(serialization_alias="createdAt")
    team_id: UUID | None = Field(serialization_alias="teamId")
    team_name: str | None = Field(serialization_alias="teamName")


class AssignmentTeamResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    team_id: UUID = Field(serialization_alias="teamId")
    name: str
    kind: str


class AssignmentTeamListResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    teams: list[AssignmentTeamResponse]


class WorkPackageResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    package_id: UUID = Field(serialization_alias="id")
    title: str
    status: str
    sort_order: int = Field(serialization_alias="sortOrder")


class AnalystNoteResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    note_id: UUID = Field(serialization_alias="id")
    body: str
    created_by_user_id: UUID = Field(serialization_alias="createdByUserId")
    created_at: datetime = Field(serialization_alias="createdAt")


class LinkedProductResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    link_id: UUID = Field(serialization_alias="id")
    product_id: UUID = Field(serialization_alias="productId")
    reference: str
    title: str
    summary: str
    created_at: datetime = Field(serialization_alias="createdAt")


class DraftAssetResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    asset_id: UUID = Field(serialization_alias="id")
    name: str
    asset_type: str = Field(serialization_alias="assetType")
    mime_type: str = Field(serialization_alias="mimeType")
    size_bytes: int = Field(serialization_alias="sizeBytes")
    sha256: str
    detected_mime_type: str = Field(serialization_alias="detectedMimeType")
    preview_kind: str = Field(serialization_alias="previewKind")
    processing_status: str = Field(serialization_alias="processingStatus")
    preview_available: bool = Field(serialization_alias="previewAvailable")


class DraftProductResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    version_id: UUID = Field(serialization_alias="id")
    version_number: int = Field(serialization_alias="versionNumber")
    title: str
    summary: str
    product_type: str = Field(serialization_alias="productType")
    content: str
    description: str
    source_type: str = Field(serialization_alias="sourceType")
    owner_team: str = Field(serialization_alias="ownerTeam")
    area_or_region: str = Field(serialization_alias="areaOrRegion")
    classification_level: int = Field(serialization_alias="classificationLevel")
    releasability: list[str]
    handling_caveats: list[str] = Field(serialization_alias="handlingCaveats")
    tags: list[str]
    acg_ids: list[UUID] = Field(serialization_alias="acgIds")
    manifest_hash: str = Field(serialization_alias="manifestHash")
    assets: list[DraftAssetResponse]
    created_at: datetime = Field(serialization_alias="createdAt")


class AnalystTaskResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    ticket_id: UUID = Field(serialization_alias="ticketId")
    reference: str
    state: str
    title: str
    description: str | None
    operational_question: str | None = Field(serialization_alias="operationalQuestion")
    area_or_region: str | None = Field(serialization_alias="areaOrRegion")
    priority: str | None
    required_output_format: str | None = Field(serialization_alias="requiredOutputFormat")
    chat_summary: list[str] = Field(serialization_alias="chatSummary")
    manager_notes: list[str] = Field(serialization_alias="managerNotes")
    assignments: list[AnalystAssignmentResponse]
    work_packages: list[WorkPackageResponse] = Field(serialization_alias="workPackages")
    notes: list[AnalystNoteResponse]
    linked_products: list[LinkedProductResponse] = Field(serialization_alias="linkedProducts")
    drafts: list[DraftProductResponse]


class AnalystTaskListResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    tasks: list[AnalystTaskResponse]


class AnalystCandidateListResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    analysts: list[AnalystCandidateResponse]
