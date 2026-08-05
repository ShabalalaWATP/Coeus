"""Domain mappings and safe errors for canonical workforce calendars."""

from collections.abc import Callable

from coeus.core.errors import AppError
from coeus.domain.workforce_calendar import (
    CalendarDeduplicationIntegrityError,
    CalendarEvent,
    CalendarIdempotencyConflict,
    CalendarMutationConflict,
    CalendarMutationDenied,
    CalendarMutationPreview,
    CalendarMutationRequest,
    CalendarOccurrence,
    CalendarProjection,
    CalendarProjectionDenied,
    CalendarRecurrence,
    CalendarRecurrenceIntegrityError,
    CalendarTiming,
)
from coeus.schemas.workforce_calendar import (
    CalendarAggregateCellResponse,
    CalendarEventPayload,
    CalendarMutationPayload,
    CalendarOccurrenceResponse,
    CalendarPreviewResponse,
    CalendarProjectionEntryResponse,
    CalendarProjectionResponse,
    CalendarRecurrencePayload,
    CalendarSnapshotResponse,
    CalendarTimingPayload,
)


def mutation_request(payload: CalendarMutationPayload) -> CalendarMutationRequest:
    return CalendarMutationRequest(
        payload.operation,
        event_from_payload(payload.event),
        payload.expected_version,
        payload.authorising_grant_id,
        payload.reason,
        payload.occurrence_key,
        payload.future_event_id,
    )


def event_from_payload(payload: CalendarEventPayload) -> CalendarEvent:
    recurrence = payload.recurrence
    timing = payload.timing
    return CalendarEvent(
        payload.event_id,
        payload.owner_user_id,
        payload.source,
        payload.activity,
        CalendarTiming(
            timing.time_zone,
            timing.starts_at,
            timing.ends_at,
            timing.all_day_start,
            timing.all_day_end,
        ),
        payload.availability,
        payload.privacy,
        payload.created_by_user_id,
        payload.note,
        None
        if recurrence is None
        else CalendarRecurrence(
            recurrence.frequency,
            recurrence.interval,
            recurrence.until,
            tuple(recurrence.weekdays),
        ),
        payload.manager_scope_unit_id,
        payload.status,
        payload.version,
        payload.created_at,
        payload.updated_at,
        payload.cancelled_at,
        (),
        payload.deduplication_key,
    )


def event_payload(event: CalendarEvent) -> CalendarEventPayload:
    recurrence = event.recurrence
    values = {
        **{key: value for key, value in vars(event).items() if key != "exceptions"},
        "timing": CalendarTimingPayload(**vars(event.timing)),
        "recurrence": (
            None if recurrence is None else CalendarRecurrencePayload(**vars(recurrence))
        ),
    }
    return CalendarEventPayload(**values)


def occurrence_payload(
    occurrence: CalendarOccurrence | CalendarEvent,
) -> CalendarOccurrenceResponse:
    if isinstance(occurrence, CalendarEvent):
        occurrence = CalendarOccurrence(occurrence.event_id, "single", occurrence)
    return CalendarOccurrenceResponse(
        **event_payload(occurrence.event).model_dump(),
        seriesEventId=occurrence.series_event_id,
        occurrenceKey=occurrence.occurrence_key,
        seriesTiming=CalendarTimingPayload(
            **vars(occurrence.series_timing or occurrence.event.timing)
        ),
        duplicateSources=list(occurrence.duplicate_sources),
    )


def preview_response(preview: CalendarMutationPreview) -> CalendarPreviewResponse:
    return CalendarPreviewResponse(
        request=CalendarMutationPayload(
            operation=preview.request.operation,
            event=event_payload(preview.request.event),
            expectedVersion=preview.request.expected_version,
            authorisingGrantId=preview.request.authorising_grant_id,
            reason=preview.request.reason,
            occurrenceKey=preview.request.occurrence_key,
            futureEventId=preview.request.future_event_id,
        ),
        snapshot=CalendarSnapshotResponse(**vars(preview.snapshot)),
        preview_hash=preview.preview_hash,
    )


def projection_response(projection: CalendarProjection) -> CalendarProjectionResponse:
    return CalendarProjectionResponse(
        rootUnitId=projection.root_unit_id,
        scope=projection.scope,
        generatedAt=projection.generated_at,
        unitIds=list(projection.unit_ids),
        memberCount=projection.member_count,
        suppressed=projection.suppressed,
        truncated=projection.truncated,
        entries=[
            CalendarProjectionEntryResponse(
                unitId=entry.unit_id,
                timing=CalendarTimingPayload(**vars(entry.timing)),
                availability=entry.availability,
                detail=entry.detail,
                eventId=entry.event_id,
                ownerUserId=entry.owner_user_id,
                activity=entry.activity,
                note=entry.note,
                seriesEventId=entry.series_event_id,
                occurrenceKey=entry.occurrence_key,
            )
            for entry in projection.entries
        ],
        aggregates=[
            CalendarAggregateCellResponse(
                unitId=cell.unit_id,
                day=cell.day,
                memberCount=cell.member_count,
                unavailableCount=cell.unavailable_count,
                suppressed=cell.suppressed,
            )
            for cell in projection.aggregates
        ],
    )


def call_calendar[T](operation: Callable[[], T]) -> T:
    try:
        return operation()
    except CalendarMutationDenied as exc:
        raise AppError(
            403,
            "calendar_change_denied",
            "You do not have authority for this calendar change.",
        ) from exc
    except CalendarProjectionDenied as exc:
        raise AppError(
            404,
            "calendar_not_found",
            "Calendar not found.",
        ) from exc
    except CalendarRecurrenceIntegrityError as exc:
        raise AppError(
            503,
            "calendar_recurrence_unavailable",
            "Calendar recurrence data is not currently available.",
        ) from exc
    except CalendarDeduplicationIntegrityError as exc:
        raise AppError(
            503,
            "calendar_overlap_unknown",
            "Calendar overlap data cannot currently be resolved safely.",
        ) from exc
    except CalendarIdempotencyConflict as exc:
        raise AppError(409, "calendar_command_conflict", str(exc)) from exc
    except CalendarMutationConflict as exc:
        raise AppError(409, "calendar_change_conflict", str(exc)) from exc
    except ValueError as exc:
        raise AppError(422, "calendar_change_invalid", str(exc)) from exc
