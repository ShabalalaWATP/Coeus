from dataclasses import replace
from datetime import UTC, date, datetime
from uuid import UUID, uuid4

import pytest

from coeus.domain.calendar_occurrence_policy import split_series, validate_occurrence_request
from coeus.domain.workforce_calendar import (
    AvailabilityEffect,
    CalendarActivity,
    CalendarEvent,
    CalendarEventSource,
    CalendarFrequency,
    CalendarMutationConflict,
    CalendarMutationOperation,
    CalendarMutationRequest,
    CalendarOccurrenceException,
    CalendarPrivacy,
    CalendarRecurrence,
    CalendarTiming,
)


def _event() -> CalendarEvent:
    owner = uuid4()
    return CalendarEvent(
        uuid4(),
        owner,
        CalendarEventSource.PERSONAL,
        CalendarActivity.TRAINING,
        CalendarTiming(
            "Europe/London", all_day_start=date(2026, 8, 10), all_day_end=date(2026, 8, 11)
        ),
        AvailabilityEffect.UNAVAILABLE,
        CalendarPrivacy.TEAM_SUMMARY,
        owner,
        recurrence=CalendarRecurrence(CalendarFrequency.DAILY, 1, date(2026, 8, 14)),
    )


def _request(
    event: CalendarEvent,
    operation: CalendarMutationOperation,
    occurrence_key: str = "2026-08-12",
    future_event_id: UUID | None = None,
) -> CalendarMutationRequest:
    return CalendarMutationRequest(
        operation,
        event,
        1,
        None,
        "Synthetic occurrence policy.",
        occurrence_key,
        future_event_id,
    )


def test_non_occurrence_operation_needs_no_series_validation() -> None:
    event = replace(_event(), recurrence=None)
    request = CalendarMutationRequest(
        CalendarMutationOperation.UPDATE, event, 1, None, "Update whole event."
    )
    validate_occurrence_request(request, event)


def test_occurrence_requires_matching_series_rule_and_real_key() -> None:
    event = _event()
    assert event.recurrence is not None
    request = _request(event, CalendarMutationOperation.UPDATE_OCCURRENCE)
    with pytest.raises(CalendarMutationConflict, match="not a recurring"):
        validate_occurrence_request(request, replace(event, recurrence=None))
    with pytest.raises(CalendarMutationConflict, match="series rule"):
        validate_occurrence_request(
            replace(
                request, event=replace(event, recurrence=replace(event.recurrence, interval=2))
            ),
            event,
        )
    with pytest.raises(CalendarMutationConflict, match="not part"):
        validate_occurrence_request(replace(request, occurrence_key="2026-08-20"), event)


def test_occurrence_rejects_cancelled_or_moved_replacement() -> None:
    event = _event()
    cancelled = replace(
        event,
        exceptions=(CalendarOccurrenceException("2026-08-12", True),),
    )
    request = _request(event, CalendarMutationOperation.UPDATE_OCCURRENCE)
    with pytest.raises(CalendarMutationConflict, match="already cancelled"):
        validate_occurrence_request(request, cancelled)
    moved = replace(
        request,
        event=replace(
            event,
            timing=CalendarTiming(
                "Europe/London",
                datetime(2026, 8, 13, 9, tzinfo=UTC),
                datetime(2026, 8, 13, 10, tzinfo=UTC),
            ),
        ),
    )
    with pytest.raises(CalendarMutationConflict, match="scheduled local date"):
        validate_occurrence_request(moved, event)
    validate_occurrence_request(_request(event, CalendarMutationOperation.CANCEL_OCCURRENCE), event)


def test_future_split_requires_non_first_new_identity_and_builds_two_series() -> None:
    event = _event()
    desired = replace(
        event,
        timing=CalendarTiming(
            "Europe/London", all_day_start=date(2026, 8, 12), all_day_end=date(2026, 8, 13)
        ),
        activity=CalendarActivity.DUTY,
    )
    request = _request(desired, CalendarMutationOperation.UPDATE_FUTURE, future_event_id=uuid4())
    validate_occurrence_request(request, event)
    parent, child = split_series(event, request)
    assert parent.recurrence and parent.recurrence.until == date(2026, 8, 11)
    assert child.event_id == request.future_event_id
    assert child.timing.start_date == date(2026, 8, 12)
    assert child.activity is CalendarActivity.DUTY and child.exceptions == ()

    with pytest.raises(CalendarMutationConflict, match="whole series"):
        validate_occurrence_request(
            replace(request, occurrence_key="2026-08-10", event=event), event
        )
    with pytest.raises(CalendarMutationConflict, match="new event ID"):
        validate_occurrence_request(replace(request, future_event_id=event.event_id), event)


def test_split_series_defensively_rejects_incomplete_identity() -> None:
    event = _event()
    update = _request(event, CalendarMutationOperation.UPDATE_OCCURRENCE)
    with pytest.raises(CalendarMutationConflict, match="identity is incomplete"):
        split_series(event, update)
    no_rule = replace(event, recurrence=None)
    forged = _request(event, CalendarMutationOperation.UPDATE_FUTURE, future_event_id=uuid4())
    with pytest.raises(CalendarMutationConflict, match="not a recurring"):
        split_series(no_rule, forged)


def test_exception_contract_rejects_ambiguous_and_duplicate_values() -> None:
    with pytest.raises(ValueError, match="cancellation or complete change"):
        CalendarOccurrenceException("2026-08-12", False)
    event = _event()
    exception = CalendarOccurrenceException("2026-08-12", True)
    with pytest.raises(ValueError, match="unique occurrence"):
        replace(event, exceptions=(exception, exception))
