"""Privacy-bounded advisory team capacity forecast contracts."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from coeus.domain.team_capacity_forecast import TeamForecastStatus


class TeamCapacityForecastResponse(BaseModel):
    model_config = ConfigDict(frozen=True, populate_by_name=True)

    unit_id: UUID = Field(alias="unitId")
    window_start: datetime = Field(alias="windowStart")
    window_end: datetime = Field(alias="windowEnd")
    status: TeamForecastStatus
    people_considered: int = Field(alias="peopleConsidered")
    people_included: int = Field(alias="peopleIncluded")
    people_unknown: int = Field(alias="peopleUnknown")
    physical_minutes: int = Field(alias="physicalMinutes")
    unavailable_minutes: int = Field(alias="unavailableMinutes")
    reservation_minutes: int = Field(alias="reservationMinutes")
    capacity_reduction_minutes: int = Field(alias="capacityReductionMinutes")
    policy_buffer_minutes: int = Field(alias="policyBufferMinutes")
    assignable_minutes: int = Field(alias="assignableMinutes")
    as_of: datetime = Field(alias="asOf")
