"""Privacy-minimised canonical personal work API contracts."""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from coeus.domain.my_work import MyWorkColumn
from coeus.domain.team_task_ownership import WorkflowLeg


class MyWorkCardResponse(BaseModel):
    model_config = ConfigDict(frozen=True, populate_by_name=True)

    ticket_id: UUID = Field(alias="ticketId")
    workflow_leg: WorkflowLeg = Field(alias="workflowLeg")
    package_id: UUID = Field(alias="packageId")
    reference: str
    ticket_title: str = Field(alias="ticketTitle")
    package_title: str = Field(alias="packageTitle")
    column: MyWorkColumn
    priority: int | None
    target_date: date | None = Field(alias="targetDate")
    due_at: datetime | None = Field(alias="dueAt")
    blocked_code: str | None = Field(alias="blockedCode")
    review_at: datetime | None = Field(alias="reviewAt")
    ticket_version: int = Field(alias="ticketVersion")
    ownership_version: int = Field(alias="ownershipVersion")
    package_version: int = Field(alias="packageVersion")


class MyWorkPageResponse(BaseModel):
    model_config = ConfigDict(frozen=True, populate_by_name=True)

    cards: list[MyWorkCardResponse]
    as_of: datetime = Field(alias="asOf")
    next_cursor: str | None = Field(alias="nextCursor")
