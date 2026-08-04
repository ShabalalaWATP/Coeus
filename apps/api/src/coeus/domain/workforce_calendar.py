"""Canonical workforce calendar records and actor-bound command contracts."""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import StrEnum
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from coeus.domain.calendar_commitments import (
    CalendarCommitment as CalendarCommitment,
)
from coeus.domain.calendar_commitments import (
    CalendarCommitmentResponse as CalendarCommitmentResponse,
)
from coeus.domain.calendar_commitments import (
    CommitmentResponseState as CommitmentResponseState,
)
from coeus.domain.calendar_enums import (
    AvailabilityEffect as AvailabilityEffect,
)
from coeus.domain.calendar_enums import (
    CalendarActivity as CalendarActivity,
)
from coeus.domain.calendar_enums import (
    CalendarEventSource as CalendarEventSource,
)
from coeus.domain.calendar_enums import (
    CalendarEventStatus as CalendarEventStatus,
)
from coeus.domain.calendar_enums import (
    CalendarFrequency as CalendarFrequency,
)
from coeus.domain.calendar_enums import (
    CalendarMutationOperation as CalendarMutationOperation,
)
from coeus.domain.calendar_enums import (
    CalendarPrivacy as CalendarPrivacy,
)
from coeus.domain.organisation_validation import aware, optional_text, text_value


class CalendarMutationDenied(PermissionError):
    pass


class CalendarMutationConflict(RuntimeError):
    pass


class CalendarProjectionDenied(PermissionError):
    pass


class CalendarIdempotencyConflict(RuntimeError):
    pass


class CalendarRecurrenceIntegrityError(RuntimeError):
    pass


class CalendarDeduplicationIntegrityError(RuntimeError):
    pass


@dataclass(frozen=True)
class CalendarRecurrence:
    frequency: CalendarFrequency
    interval: int
    until: date
    weekdays: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        if not 1 <= self.interval <= 52:
            raise ValueError("recurrence interval must be between one and 52")
        if len(self.weekdays) != len(set(self.weekdays)) or any(
            day < 0 or day > 6 for day in self.weekdays
        ):
            raise ValueError("recurrence weekdays must be unique values from zero to six")
        if self.frequency is CalendarFrequency.WEEKLY and not self.weekdays:
            raise ValueError("weekly recurrence requires at least one weekday")
        if self.frequency is CalendarFrequency.DAILY and self.weekdays:
            raise ValueError("daily recurrence does not accept weekdays")


@dataclass(frozen=True)
class CalendarTiming:
    time_zone: str
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    all_day_start: date | None = None
    all_day_end: date | None = None

    def __post_init__(self) -> None:
        try:
            ZoneInfo(self.time_zone)
        except ZoneInfoNotFoundError as error:
            raise ValueError("time_zone is not recognised") from error
        timed = self.starts_at is not None or self.ends_at is not None
        all_day = self.all_day_start is not None or self.all_day_end is not None
        if timed == all_day:
            raise ValueError("calendar timing must be either timed or all-day")
        if timed:
            aware(self.starts_at, "starts_at")
            aware(self.ends_at, "ends_at")
            if self.starts_at is None or self.ends_at is None or self.ends_at <= self.starts_at:
                raise ValueError("ends_at must follow starts_at")
        elif (
            self.all_day_start is None
            or self.all_day_end is None
            or self.all_day_end <= self.all_day_start
        ):
            raise ValueError("all_day_end must follow all_day_start")

    @property
    def start_date(self) -> date:
        if self.all_day_start is not None:
            return self.all_day_start
        if self.starts_at is None:
            raise ValueError("calendar timing has no start")
        return self.starts_at.astimezone(ZoneInfo(self.time_zone)).date()


@dataclass(frozen=True)
class CalendarOccurrenceException:
    occurrence_key: str
    cancelled: bool
    timing: CalendarTiming | None = None
    activity: CalendarActivity | None = None
    availability: AvailabilityEffect | None = None
    privacy: CalendarPrivacy | None = None
    note: str | None = None

    def __post_init__(self) -> None:
        date.fromisoformat(self.occurrence_key)
        if self.note is not None:
            optional_text(self.note, "exception note", 280)
        details = (self.activity, self.availability, self.privacy, self.note)
        changed = self.timing is not None and all(value is not None for value in details)
        if self.cancelled == changed:
            raise ValueError("calendar exception must be a cancellation or complete change")


@dataclass(frozen=True)
class CalendarEvent:
    event_id: UUID
    owner_user_id: UUID
    source: CalendarEventSource
    activity: CalendarActivity
    timing: CalendarTiming
    availability: AvailabilityEffect
    privacy: CalendarPrivacy
    created_by_user_id: UUID
    note: str = ""
    recurrence: CalendarRecurrence | None = None
    manager_scope_unit_id: UUID | None = None
    status: CalendarEventStatus = CalendarEventStatus.ACTIVE
    version: int = 1
    created_at: datetime | None = None
    updated_at: datetime | None = None
    cancelled_at: datetime | None = None
    exceptions: tuple[CalendarOccurrenceException, ...] = ()
    deduplication_key: str | None = None

    def __post_init__(self) -> None:
        optional_text(self.note, "note", 280)
        if self.version < 1:
            raise ValueError("calendar event version must be positive")
        aware(self.created_at, "created_at")
        aware(self.updated_at, "updated_at")
        aware(self.cancelled_at, "cancelled_at")
        if self.source in {CalendarEventSource.MANAGER, CalendarEventSource.TEAM} and (
            self.manager_scope_unit_id is None
        ):
            raise ValueError("manager and team events require a scope unit")
        if (
            self.source not in {CalendarEventSource.MANAGER, CalendarEventSource.TEAM}
            and self.manager_scope_unit_id is not None
        ):
            raise ValueError("only manager and team events may name a scope unit")
        if self.deduplication_key is not None:
            optional_text(self.deduplication_key, "deduplication key", 128)
        if (self.status is CalendarEventStatus.CANCELLED) != (self.cancelled_at is not None):
            raise ValueError("cancelled events require a cancellation timestamp")
        if self.recurrence is not None:
            if self.recurrence.until < self.timing.start_date:
                raise ValueError("recurrence cannot end before the first occurrence")
            if self.recurrence.until > self.timing.start_date + timedelta(days=366):
                raise ValueError("recurrence cannot exceed 366 days")
        keys = tuple(item.occurrence_key for item in self.exceptions)
        if len(keys) != len(set(keys)):
            raise ValueError("calendar exceptions require unique occurrence keys")


@dataclass(frozen=True)
class CalendarOccurrence:
    series_event_id: UUID
    occurrence_key: str
    event: CalendarEvent
    series_timing: CalendarTiming | None = None
    duplicate_sources: tuple[CalendarEventSource, ...] = ()


@dataclass(frozen=True)
class CalendarMutationRequest:
    operation: CalendarMutationOperation
    event: CalendarEvent
    expected_version: int
    authorising_grant_id: UUID | None
    reason: str
    occurrence_key: str | None = None
    future_event_id: UUID | None = None

    def __post_init__(self) -> None:
        text_value(self.reason, "reason", 500)
        if self.operation is CalendarMutationOperation.CREATE and self.expected_version != 0:
            raise ValueError("create expected_version must be zero")
        if self.operation is not CalendarMutationOperation.CREATE and self.expected_version < 1:
            raise ValueError("update and cancel expected_version must be positive")
        occurrence_operation = self.operation in {
            CalendarMutationOperation.UPDATE_OCCURRENCE,
            CalendarMutationOperation.CANCEL_OCCURRENCE,
            CalendarMutationOperation.UPDATE_FUTURE,
        }
        if occurrence_operation != (self.occurrence_key is not None):
            raise ValueError("occurrence operations require exactly one occurrence key")
        if self.occurrence_key is not None:
            date.fromisoformat(self.occurrence_key)
        if (self.operation is CalendarMutationOperation.UPDATE_FUTURE) != (
            self.future_event_id is not None
        ):
            raise ValueError("future edits require exactly one new series event ID")


@dataclass(frozen=True)
class CalendarMutationSnapshot:
    current_version: int
    overlapping_events: int
    state_digest: str

    def __post_init__(self) -> None:
        if self.current_version < 0 or self.overlapping_events < 0:
            raise ValueError("calendar snapshot counts must be non-negative")
        _digest(self.state_digest, "state_digest")


@dataclass(frozen=True)
class CalendarMutationPreview:
    request: CalendarMutationRequest
    snapshot: CalendarMutationSnapshot
    preview_hash: str

    def __post_init__(self) -> None:
        _digest(self.preview_hash, "preview_hash")


@dataclass(frozen=True)
class CalendarMutationCommand:
    command_id: UUID
    idempotency_key: str
    actor_user_id: UUID
    request: CalendarMutationRequest
    preview_hash: str

    def __post_init__(self) -> None:
        text_value(self.idempotency_key, "idempotency_key", 128)
        _digest(self.preview_hash, "preview_hash")


@dataclass(frozen=True)
class CalendarMutationResult:
    event_id: UUID
    version: int
    replayed: bool = False
    future_event_id: UUID | None = None


class CalendarProjectionScope(StrEnum):
    DIRECT = "direct"
    DESCENDANTS = "descendants"


class CalendarProjectionDetail(StrEnum):
    SELF = "self"
    DETAIL = "detail"
    AVAILABILITY = "availability"


@dataclass(frozen=True)
class ScopedCalendarEvent:
    unit_id: UUID
    event: CalendarEvent


@dataclass(frozen=True)
class ScopedCalendarOccurrence:
    unit_id: UUID
    occurrence: CalendarOccurrence


@dataclass(frozen=True)
class CalendarProjectionEntry:
    unit_id: UUID
    timing: CalendarTiming
    availability: AvailabilityEffect
    detail: CalendarProjectionDetail
    event_id: UUID | None = None
    owner_user_id: UUID | None = None
    activity: CalendarActivity | None = None
    note: str | None = None
    series_event_id: UUID | None = None
    occurrence_key: str | None = None


@dataclass(frozen=True)
class CalendarAggregateCell:
    unit_id: UUID
    day: date
    member_count: int | None
    unavailable_count: int | None
    suppressed: bool


@dataclass(frozen=True)
class CalendarProjection:
    root_unit_id: UUID
    scope: CalendarProjectionScope
    generated_at: datetime
    unit_ids: tuple[UUID, ...]
    member_count: int | None
    suppressed: bool
    truncated: bool
    entries: tuple[CalendarProjectionEntry, ...]
    aggregates: tuple[CalendarAggregateCell, ...] = ()


def _digest(value: str, label: str) -> None:
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise ValueError(f"{label} must be a lowercase SHA-256 digest")
