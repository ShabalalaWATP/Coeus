"""HTTP schemas for canonical personal and manager calendar events."""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from coeus.domain.workforce_calendar import (
    AvailabilityEffect,
    CalendarActivity,
    CalendarEventSource,
    CalendarEventStatus,
    CalendarFrequency,
    CalendarMutationOperation,
    CalendarPrivacy,
    CalendarProjectionDetail,
    CalendarProjectionScope,
    CommitmentResponseState,
)


class CalendarRecurrencePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    frequency: CalendarFrequency
    interval: int = Field(ge=1, le=52)
    until: date
    weekdays: list[int] = Field(default_factory=list, max_length=7)


class CalendarTimingPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    time_zone: str = Field(alias="timeZone", min_length=1, max_length=64)
    starts_at: datetime | None = Field(default=None, alias="startsAt")
    ends_at: datetime | None = Field(default=None, alias="endsAt")
    all_day_start: date | None = Field(default=None, alias="allDayStart")
    all_day_end: date | None = Field(default=None, alias="allDayEnd")


class CalendarEventPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    event_id: UUID = Field(alias="eventId")
    owner_user_id: UUID = Field(alias="ownerUserId")
    source: CalendarEventSource
    activity: CalendarActivity
    timing: CalendarTimingPayload
    availability: AvailabilityEffect
    privacy: CalendarPrivacy
    created_by_user_id: UUID = Field(alias="createdByUserId")
    note: str = Field(default="", max_length=280)
    recurrence: CalendarRecurrencePayload | None = None
    manager_scope_unit_id: UUID | None = Field(default=None, alias="managerScopeUnitId")
    status: CalendarEventStatus = CalendarEventStatus.ACTIVE
    version: int = Field(default=1, ge=1)
    created_at: datetime | None = Field(default=None, alias="createdAt")
    updated_at: datetime | None = Field(default=None, alias="updatedAt")
    cancelled_at: datetime | None = Field(default=None, alias="cancelledAt")
    deduplication_key: str | None = Field(default=None, alias="deduplicationKey", max_length=128)


class CalendarMutationPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    operation: CalendarMutationOperation
    event: CalendarEventPayload
    expected_version: int = Field(alias="expectedVersion", ge=0)
    authorising_grant_id: UUID | None = Field(default=None, alias="authorisingGrantId")
    reason: str = Field(min_length=1, max_length=500)
    occurrence_key: str | None = Field(default=None, alias="occurrenceKey", max_length=10)
    future_event_id: UUID | None = Field(default=None, alias="futureEventId")


class CalendarSnapshotResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    current_version: int = Field(serialization_alias="currentVersion")
    overlapping_events: int = Field(serialization_alias="overlappingEvents")
    state_digest: str = Field(serialization_alias="stateDigest")


class CalendarPreviewResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    request: CalendarMutationPayload
    snapshot: CalendarSnapshotResponse
    preview_hash: str = Field(serialization_alias="previewHash")


class CalendarCommandPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    command_id: UUID = Field(alias="commandId")
    idempotency_key: str = Field(alias="idempotencyKey", min_length=1, max_length=128)
    request: CalendarMutationPayload
    preview_hash: str = Field(alias="previewHash", pattern=r"^[0-9a-f]{64}$")


class CalendarMutationResultResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    event_id: UUID = Field(serialization_alias="eventId")
    version: int
    replayed: bool
    future_event_id: UUID | None = Field(default=None, serialization_alias="futureEventId")


class CalendarOccurrenceResponse(CalendarEventPayload):
    series_event_id: UUID = Field(alias="seriesEventId")
    occurrence_key: str = Field(alias="occurrenceKey", min_length=1, max_length=64)
    series_timing: CalendarTimingPayload = Field(alias="seriesTiming")
    duplicate_sources: list[CalendarEventSource] = Field(
        default_factory=list, alias="duplicateSources"
    )


class CalendarEventListResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    events: list[CalendarOccurrenceResponse]


class CalendarCommitmentResponsePayload(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    state: CommitmentResponseState
    expected_version: int = Field(alias="expectedVersion", ge=1)
    reason: str = Field(default="", max_length=500)


class CalendarCommitmentPayload(BaseModel):
    model_config = ConfigDict(frozen=True, populate_by_name=True)

    event: CalendarEventPayload
    response_state: CommitmentResponseState = Field(alias="responseState")
    response_version: int = Field(alias="responseVersion")
    notified_at: datetime = Field(alias="notifiedAt")
    responded_at: datetime | None = Field(default=None, alias="respondedAt")


class CalendarCommitmentListResponse(BaseModel):
    commitments: list[CalendarCommitmentPayload]


class CalendarProjectionEntryResponse(BaseModel):
    model_config = ConfigDict(frozen=True, populate_by_name=True)

    unit_id: UUID = Field(alias="unitId")
    timing: CalendarTimingPayload
    availability: AvailabilityEffect
    detail: CalendarProjectionDetail
    event_id: UUID | None = Field(default=None, alias="eventId")
    owner_user_id: UUID | None = Field(default=None, alias="ownerUserId")
    activity: CalendarActivity | None = None
    note: str | None = None
    series_event_id: UUID | None = Field(default=None, alias="seriesEventId")
    occurrence_key: str | None = Field(default=None, alias="occurrenceKey")


class CalendarAggregateCellResponse(BaseModel):
    model_config = ConfigDict(frozen=True, populate_by_name=True)

    unit_id: UUID = Field(alias="unitId")
    day: date
    member_count: int | None = Field(alias="memberCount")
    unavailable_count: int | None = Field(alias="unavailableCount")
    suppressed: bool


class CalendarProjectionResponse(BaseModel):
    model_config = ConfigDict(frozen=True, populate_by_name=True)

    root_unit_id: UUID = Field(alias="rootUnitId")
    scope: CalendarProjectionScope
    generated_at: datetime = Field(alias="generatedAt")
    unit_ids: list[UUID] = Field(alias="unitIds")
    member_count: int | None = Field(alias="memberCount")
    suppressed: bool
    truncated: bool
    entries: list[CalendarProjectionEntryResponse]
    aggregates: list[CalendarAggregateCellResponse]
