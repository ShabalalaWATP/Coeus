"""Public privacy-minimised team task board contracts."""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from coeus.domain.team_task_board import TeamBoardColumn, TeamBoardScope
from coeus.domain.team_task_ownership import WorkflowLeg


class TeamTaskPackageResponse(BaseModel):
    model_config = ConfigDict(frozen=True, populate_by_name=True)

    package_id: UUID = Field(alias="packageId")
    title: str
    state: str
    accountable_user_id: UUID | None = Field(alias="accountableUserId")
    estimated_minutes: int | None = Field(alias="estimatedMinutes")
    remaining_minutes: int | None = Field(alias="remainingMinutes")
    due_at: datetime | None = Field(alias="dueAt")
    priority: int | None
    version: int


class TeamTaskCardResponse(BaseModel):
    model_config = ConfigDict(frozen=True, populate_by_name=True)

    ticket_id: UUID = Field(alias="ticketId")
    workflow_leg: WorkflowLeg = Field(alias="workflowLeg")
    reference: str
    title: str
    column: TeamBoardColumn
    priority: str
    target_date: date | None = Field(alias="targetDate")
    ticket_updated_at: datetime = Field(alias="ticketUpdatedAt")
    ticket_version: int = Field(alias="ticketVersion")
    ownership_version: int = Field(alias="ownershipVersion")
    packages: list[TeamTaskPackageResponse]
    unit_id: UUID | None = Field(default=None, alias="unitId")
    unit_name: str | None = Field(default=None, alias="unitName")


class TeamBoardAggregateResponse(BaseModel):
    model_config = ConfigDict(frozen=True, populate_by_name=True)

    unit_id: UUID = Field(alias="unitId")
    unit_name: str = Field(alias="unitName")
    column: TeamBoardColumn
    count: int | None = Field(default=None, ge=0)
    suppressed: bool


class TeamTaskBoardResponse(BaseModel):
    model_config = ConfigDict(frozen=True, populate_by_name=True)

    unit_id: UUID = Field(alias="unitId")
    cards: list[TeamTaskCardResponse]
    as_of: datetime = Field(alias="asOf")
    truncated: bool
    next_cursor: str | None = Field(alias="nextCursor")
    aggregates: list[TeamBoardAggregateResponse]
    scope: TeamBoardScope
