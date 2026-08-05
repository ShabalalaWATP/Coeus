"""Fail-closed policy for mutations scoped to one occurrence or future series."""

from dataclasses import replace
from datetime import UTC, datetime, time, timedelta

from coeus.domain.calendar_recurrence import ExpandedOccurrence, expand_occurrences
from coeus.domain.workforce_calendar import (
    CalendarEvent,
    CalendarMutationConflict,
    CalendarMutationOperation,
    CalendarMutationRequest,
    CalendarRecurrence,
)

OCCURRENCE_OPERATIONS = frozenset(
    {
        CalendarMutationOperation.UPDATE_OCCURRENCE,
        CalendarMutationOperation.CANCEL_OCCURRENCE,
        CalendarMutationOperation.UPDATE_FUTURE,
    }
)


def validate_occurrence_request(request: CalendarMutationRequest, existing: CalendarEvent) -> None:
    if request.operation not in OCCURRENCE_OPERATIONS:
        return
    recurrence = existing.recurrence
    if recurrence is None or request.occurrence_key is None:
        raise CalendarMutationConflict("the calendar event is not a recurring series")
    if request.event.recurrence != recurrence or request.event.exceptions:
        raise CalendarMutationConflict("occurrence changes cannot alter the series rule")
    occurrences = _series_occurrences(existing, recurrence)
    occurrence = next(
        (item for item in occurrences if item.occurrence_key == request.occurrence_key), None
    )
    if occurrence is None:
        raise CalendarMutationConflict("the occurrence is not part of this series")
    prior = next(
        (item for item in existing.exceptions if item.occurrence_key == request.occurrence_key),
        None,
    )
    if prior is not None and prior.cancelled:
        raise CalendarMutationConflict("the occurrence is already cancelled")
    if (
        request.operation is not CalendarMutationOperation.CANCEL_OCCURRENCE
        and request.event.timing.start_date != occurrence.timing.start_date
    ):
        raise CalendarMutationConflict("an occurrence must remain on its scheduled local date")
    if request.operation is CalendarMutationOperation.UPDATE_FUTURE:
        _validate_future_identity(request, existing, occurrences[0].occurrence_key)


def _validate_future_identity(
    request: CalendarMutationRequest, existing: CalendarEvent, first_key: str
) -> None:
    if request.occurrence_key == first_key:
        raise CalendarMutationConflict("edit the whole series from its first occurrence")
    if request.future_event_id == existing.event_id:
        raise CalendarMutationConflict("the future series requires a new event ID")


def split_series(
    existing: CalendarEvent, request: CalendarMutationRequest
) -> tuple[CalendarEvent, CalendarEvent]:
    if request.occurrence_key is None or request.future_event_id is None:
        raise CalendarMutationConflict("future series identity is incomplete")
    split_day = datetime.fromisoformat(request.occurrence_key).date()
    recurrence = existing.recurrence
    if recurrence is None:
        raise CalendarMutationConflict("the calendar event is not a recurring series")
    parent = replace(
        existing,
        recurrence=replace(recurrence, until=split_day - timedelta(days=1)),
        exceptions=tuple(
            item for item in existing.exceptions if item.occurrence_key < request.occurrence_key
        ),
    )
    child = replace(
        request.event,
        event_id=request.future_event_id,
        timing=request.event.timing,
        recurrence=CalendarRecurrence(
            recurrence.frequency, recurrence.interval, recurrence.until, recurrence.weekdays
        ),
        version=1,
        created_at=None,
        updated_at=None,
        cancelled_at=None,
        exceptions=(),
    )
    return parent, child


def _series_occurrences(
    event: CalendarEvent, recurrence: CalendarRecurrence
) -> tuple[ExpandedOccurrence, ...]:
    zone_start = datetime.combine(event.timing.start_date, time.min, UTC) - timedelta(days=2)
    zone_end = datetime.combine(recurrence.until, time.max, UTC) + timedelta(days=2)
    return expand_occurrences(event.timing, recurrence, zone_start, zone_end)
