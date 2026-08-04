"""Public contracts for saved views, templates and work updates."""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from coeus.domain.team_task_board import TeamBoardColumn, TeamBoardScope
from coeus.domain.workspace_productivity import DeliveryMode, WorkUpdateKind


class BoardFiltersPayload(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    scope: TeamBoardScope = TeamBoardScope.DIRECT
    include_completed: bool = Field(False, alias="includeCompleted")
    columns: list[TeamBoardColumn] = Field(default_factory=list, max_length=9)
    unit_ids: list[UUID] = Field(default_factory=list, max_length=20, alias="unitIds")
    priority: str | None = Field(None, min_length=1, max_length=40)
    due_from: date | None = Field(None, alias="dueFrom")
    due_to: date | None = Field(None, alias="dueTo")


class CommandPayload(BaseModel):
    command_id: UUID = Field(alias="commandId")
    idempotency_key: str = Field(min_length=1, max_length=128, alias="idempotencyKey")


class SaveViewPayload(CommandPayload):
    view_id: UUID = Field(alias="viewId")
    name: str = Field(min_length=1, max_length=80)
    expected_version: int = Field(ge=0, alias="expectedVersion")
    filters: BoardFiltersPayload


class DeleteRecordPayload(CommandPayload):
    expected_version: int = Field(ge=1, alias="expectedVersion")
    authorising_grant_id: UUID | None = Field(None, alias="authorisingGrantId")
    expected_grant_version: int | None = Field(None, ge=1, alias="expectedGrantVersion")


class DeleteTemplatePayload(CommandPayload):
    expected_version: int = Field(ge=1, alias="expectedVersion")
    authorising_grant_id: UUID = Field(alias="authorisingGrantId")
    expected_grant_version: int = Field(ge=1, alias="expectedGrantVersion")


class SaveTemplatePayload(CommandPayload):
    template_id: UUID = Field(alias="templateId")
    name: str = Field(min_length=1, max_length=80)
    package_titles: list[str] = Field(min_length=1, max_length=20, alias="packageTitles")
    estimated_minutes: int | None = Field(None, ge=15, le=10080, alias="estimatedMinutes")
    priority: int | None = Field(None, ge=1, le=5)
    expected_version: int = Field(ge=0, alias="expectedVersion")
    authorising_grant_id: UUID = Field(alias="authorisingGrantId")
    expected_grant_version: int = Field(ge=1, alias="expectedGrantVersion")


class AcknowledgeUpdatePayload(CommandPayload):
    pass


class SaveStoreLinkPayload(CommandPayload):
    link_id: UUID = Field(alias="linkId")
    source_type: str = Field(pattern="^(ticket|work_package)$", alias="sourceType")
    source_id: UUID = Field(alias="sourceId")
    target_type: str = Field(pattern="^(project|product)$", alias="targetType")
    target_id: UUID = Field(alias="targetId")
    expected_version: int = Field(ge=0, alias="expectedVersion")


class SavePreferencesPayload(CommandPayload):
    mode: DeliveryMode
    due_reminders: bool = Field(alias="dueReminders")
    expected_version: int = Field(ge=0, alias="expectedVersion")


class SavedViewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    view_id: UUID = Field(alias="viewId")
    owner_user_id: UUID = Field(alias="ownerUserId")
    unit_id: UUID = Field(alias="unitId")
    name: str
    filters: BoardFiltersPayload
    version: int
    updated_at: datetime = Field(alias="updatedAt")


class TemplateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    template_id: UUID = Field(alias="templateId")
    unit_id: UUID = Field(alias="unitId")
    owner_user_id: UUID = Field(alias="ownerUserId")
    name: str
    package_titles: tuple[str, ...] = Field(alias="packageTitles")
    estimated_minutes: int | None = Field(alias="estimatedMinutes")
    priority: int | None
    version: int
    updated_at: datetime = Field(alias="updatedAt")


class WorkUpdateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    update_id: UUID = Field(alias="updateId")
    kind: WorkUpdateKind
    unit_id: UUID = Field(alias="unitId")
    object_type: str = Field(alias="objectType")
    object_id: UUID = Field(alias="objectId")
    occurred_at: datetime = Field(alias="occurredAt")
    acknowledged_at: datetime | None = Field(alias="acknowledgedAt")


class PreferencesResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    mode: DeliveryMode
    due_reminders: bool = Field(alias="dueReminders")
    version: int


class StoreLinkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    link_id: UUID = Field(alias="linkId")
    unit_id: UUID = Field(alias="unitId")
    source_type: str = Field(alias="sourceType")
    source_id: UUID = Field(alias="sourceId")
    target_type: str = Field(alias="targetType")
    target_id: UUID = Field(alias="targetId")
    label: str
    version: int
    updated_at: datetime = Field(alias="updatedAt")


class SavedViewPage(BaseModel):
    items: list[SavedViewResponse]
    next_cursor: UUID | None = Field(alias="nextCursor")


class TemplatePage(BaseModel):
    items: list[TemplateResponse]
    next_cursor: UUID | None = Field(alias="nextCursor")


class WorkUpdatePage(BaseModel):
    items: list[WorkUpdateResponse]
    next_cursor: UUID | None = Field(alias="nextCursor")


class StoreLinkPage(BaseModel):
    items: list[StoreLinkResponse]
    next_cursor: UUID | None = Field(alias="nextCursor")
