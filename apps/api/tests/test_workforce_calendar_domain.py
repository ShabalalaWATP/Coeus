"""Canonical calendar domain validation and hash evidence."""

from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest

from coeus.domain.calendar_mutation_hash import calendar_preview_hash
from coeus.domain.workforce_calendar import (
    AvailabilityEffect,
    CalendarActivity,
    CalendarEvent,
    CalendarEventSource,
    CalendarFrequency,
    CalendarMutationOperation,
    CalendarMutationRequest,
    CalendarMutationSnapshot,
    CalendarPrivacy,
    CalendarRecurrence,
    CalendarTiming,
)

NOW = datetime(2026, 8, 3, 10, tzinfo=UTC)


def event() -> CalendarEvent:
    return CalendarEvent(
        uuid4(),
        uuid4(),
        CalendarEventSource.PERSONAL,
        CalendarActivity.LEAVE,
        CalendarTiming(
            "Europe/London", all_day_start=date(2026, 8, 4), all_day_end=date(2026, 8, 6)
        ),
        AvailabilityEffect.UNAVAILABLE,
        CalendarPrivacy.PRIVATE,
        uuid4(),
        "Synthetic leave",
    )


def test_validates_timed_all_day_and_bounded_recurrence() -> None:
    timed = CalendarTiming("Europe/London", NOW, NOW + timedelta(hours=2))
    assert timed.start_date == date(2026, 8, 3)
    recurrence = CalendarRecurrence(CalendarFrequency.WEEKLY, 1, date(2026, 9, 1), (0, 2))
    assert replace(event(), recurrence=recurrence).recurrence == recurrence
    with pytest.raises(ValueError, match="either timed or all-day"):
        CalendarTiming(
            "Europe/London", NOW, NOW + timedelta(hours=1), date(2026, 8, 3), date(2026, 8, 4)
        )
    with pytest.raises(ValueError, match="366"):
        replace(event(), recurrence=replace(recurrence, until=date(2028, 1, 1)))


def test_requires_manager_scope_and_valid_command_versions() -> None:
    with pytest.raises(ValueError, match="scope unit"):
        replace(event(), source=CalendarEventSource.MANAGER)
    request = CalendarMutationRequest(
        CalendarMutationOperation.CREATE, event(), 0, None, "Create leave."
    )
    digest = calendar_preview_hash(
        request,
        uuid4(),
        CalendarMutationSnapshot(0, 1, "a" * 64),
    )
    assert len(digest) == 64
    with pytest.raises(ValueError, match="expected_version"):
        replace(request, expected_version=1)


def test_occurrence_operations_require_bounded_identity_fields() -> None:
    current = event()
    occurrence = CalendarMutationRequest(
        CalendarMutationOperation.CANCEL_OCCURRENCE,
        current,
        1,
        None,
        "Cancel this occurrence.",
        "2026-08-04",
    )
    assert occurrence.occurrence_key == "2026-08-04"
    with pytest.raises(ValueError, match="occurrence key"):
        replace(occurrence, occurrence_key=None)
    with pytest.raises(ValueError, match="new series event ID"):
        replace(occurrence, operation=CalendarMutationOperation.UPDATE_FUTURE)
    with pytest.raises(ValueError):
        replace(occurrence, occurrence_key="not-a-date")
