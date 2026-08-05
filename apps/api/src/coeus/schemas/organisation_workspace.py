"""Public contracts for actor-scoped organisation workspaces."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from coeus.domain.organisation import OrganisationCategory
from coeus.domain.organisation_workspace import WorkspaceRelationship


class OrganisationWorkspaceUnitResponse(BaseModel):
    model_config = ConfigDict(frozen=True, populate_by_name=True)

    unit_id: UUID = Field(alias="id")
    name: str
    short_name: str = Field(alias="shortName")
    category: OrganisationCategory
    time_zone: str = Field(alias="timeZone")


class OrganisationWorkspaceResponse(BaseModel):
    model_config = ConfigDict(frozen=True, populate_by_name=True)

    unit: OrganisationWorkspaceUnitResponse
    relationship: WorkspaceRelationship
    managed: bool
    include_descendants: bool = Field(alias="includeDescendants")
    can_view_availability: bool = Field(alias="canViewAvailability")
    can_view_detail: bool = Field(alias="canViewDetail")
    can_view_tasks: bool = Field(alias="canViewTasks")
    planning_grant_id: UUID | None = Field(alias="planningGrantId")
    configuration_grant_id: UUID | None = Field(alias="configurationGrantId")
    configuration_grant_version: int | None = Field(alias="configurationGrantVersion")
    calendar_management_grant_id: UUID | None = Field(alias="calendarManagementGrantId")
    can_view_people: bool = Field(alias="canViewPeople")
    can_view_capabilities: bool = Field(alias="canViewCapabilities")
    can_configure: bool = Field(alias="canConfigure")
    export_grant_id: UUID | None = Field(alias="exportGrantId")
    export_grant_version: int | None = Field(alias="exportGrantVersion")


class OrganisationWorkspaceListResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    workspaces: list[OrganisationWorkspaceResponse]
    as_of: datetime = Field(serialization_alias="asOf")
    truncated: bool
