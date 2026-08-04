"""Privacy-bounded advisory team capacity forecast."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class TeamForecastStatus(StrEnum):
    READY = "ready"
    PARTIAL = "partial"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class TeamCapacityForecast:
    unit_id: UUID
    window_start: datetime
    window_end: datetime
    status: TeamForecastStatus
    people_considered: int
    people_included: int
    people_unknown: int
    physical_minutes: int
    unavailable_minutes: int
    reservation_minutes: int
    capacity_reduction_minutes: int
    policy_buffer_minutes: int
    assignable_minutes: int
    as_of: datetime

    def __post_init__(self) -> None:
        if self.window_start.tzinfo is None or self.window_end.tzinfo is None:
            raise ValueError("forecast bounds must be timezone-aware")
        if self.window_start >= self.window_end:
            raise ValueError("forecast end must follow its start")
        people = (self.people_considered, self.people_included, self.people_unknown)
        if any(value < 0 for value in people):
            raise ValueError("forecast people counts cannot be negative")
        if self.people_included + self.people_unknown != self.people_considered:
            raise ValueError("forecast people counts must reconcile")
        minutes = (
            self.physical_minutes,
            self.unavailable_minutes,
            self.reservation_minutes,
            self.capacity_reduction_minutes,
            self.policy_buffer_minutes,
            self.assignable_minutes,
        )
        if any(value < 0 or value % 15 for value in minutes):
            raise ValueError("forecast values must use non-negative 15-minute increments")


class TeamCapacityForecastDenied(PermissionError):
    pass


class TeamCapacityForecastIntegrityError(RuntimeError):
    pass
