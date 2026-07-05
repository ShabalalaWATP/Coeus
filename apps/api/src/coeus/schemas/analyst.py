from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AnalystAssignmentRequest(BaseModel):
    analyst_user_id: UUID = Field(validation_alias="analystUserId")
    work_packages: list[str] = Field(
        default_factory=list,
        max_length=8,
        validation_alias="workPackages",
    )


class AnalystNoteRequest(BaseModel):
    body: str = Field(min_length=3, max_length=2_000)


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


class DraftProductResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    version_id: UUID = Field(serialization_alias="id")
    version_number: int = Field(serialization_alias="versionNumber")
    title: str
    summary: str
    product_type: str = Field(serialization_alias="productType")
    content: str
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
    assignment: AnalystAssignmentResponse | None
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
