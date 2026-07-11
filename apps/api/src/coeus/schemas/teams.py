from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

SpecialismText = Annotated[str, Field(min_length=2, max_length=80)]


class TeamMemberRequest(BaseModel):
    user_id: UUID = Field(validation_alias="userId")


class CalendarEntryRequest(BaseModel):
    user_id: UUID = Field(validation_alias="userId")
    entry_date: str = Field(
        validation_alias="date", pattern=r"^\d{4}-\d{2}-\d{2}$", min_length=10, max_length=10
    )
    status: str = Field(pattern="^(available|on_task|leave)$")
    note: str = Field(default="", max_length=280)


class ProfileUpdateRequest(BaseModel):
    title: str = Field(default="", max_length=120)
    specialisms: list[SpecialismText] = Field(default_factory=list, max_length=8)
    bio: str = Field(default="", max_length=1_000)


class TeamMemberResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    user_id: UUID = Field(serialization_alias="userId")
    username: str
    display_name: str = Field(serialization_alias="displayName")
    is_manager: bool = Field(serialization_alias="isManager")
    title: str
    specialisms: list[str]
    bio: str


class TeamMemberCandidateListResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    users: list[TeamMemberResponse]


class TeamResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    team_id: UUID = Field(serialization_alias="id")
    name: str
    kind: str
    capability_team_id: str | None = Field(serialization_alias="capabilityTeamId")
    members: list[TeamMemberResponse]


class TeamListResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    teams: list[TeamResponse]


class CalendarEntryResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    entry_id: UUID = Field(serialization_alias="id")
    user_id: UUID = Field(serialization_alias="userId")
    entry_date: str = Field(serialization_alias="date")
    status: str
    note: str
    created_by_user_id: UUID | None = Field(serialization_alias="createdByUserId")


class CalendarResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    entries: list[CalendarEntryResponse]


class AvailabilityResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    team_id: UUID = Field(serialization_alias="teamId")
    entry_date: str = Field(serialization_alias="date")
    members: int
    on_leave: int = Field(serialization_alias="onLeave")
    on_task_calendar: int = Field(serialization_alias="onTaskCalendar")
    assigned_live: int = Field(serialization_alias="assignedLive")
    free: int


class ProfileResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    user_id: UUID = Field(serialization_alias="userId")
    title: str
    specialisms: list[str]
    bio: str
    updated_at: datetime = Field(serialization_alias="updatedAt")
