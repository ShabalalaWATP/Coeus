"""Commitment response rules and the guards around recurrence exceptions."""

from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from coeus.domain.calendar_commitments import (
    CalendarCommitmentResponse,
    CommitmentResponseState,
)
from coeus.domain.calendar_recurrence import _apply_exception
from coeus.domain.workforce_calendar import (
    AvailabilityEffect,
    CalendarActivity,
    CalendarEvent,
    CalendarEventSource,
    CalendarFrequency,
    CalendarMutationDenied,
    CalendarOccurrenceException,
    CalendarPrivacy,
    CalendarRecurrence,
    CalendarTiming,
)
from coeus.services.workforce_calendar import WorkforceCalendarService

NOW = datetime(2026, 8, 5, 12, tzinfo=UTC)
OWNER = uuid4()


def _timing(offset_days: int = 1) -> CalendarTiming:
    return CalendarTiming(
        "Europe/London",
        starts_at=NOW + timedelta(days=offset_days),
        ends_at=NOW + timedelta(days=offset_days, hours=1),
    )


def _event(**overrides: object) -> CalendarEvent:
    values: dict[str, object] = {
        "event_id": uuid4(),
        "owner_user_id": OWNER,
        "source": CalendarEventSource.PERSONAL,
        "activity": CalendarActivity.TRAINING,
        "timing": _timing(),
        "availability": AvailabilityEffect.PARTIAL,
        "privacy": CalendarPrivacy.PRIVATE,
        "created_by_user_id": OWNER,
    }
    values.update(overrides)
    return CalendarEvent(**values)  # type: ignore[arg-type]


def _response(**overrides: object) -> CalendarCommitmentResponse:
    values: dict[str, object] = {
        "event_id": uuid4(),
        "subject_user_id": OWNER,
        "state": CommitmentResponseState.ACKNOWLEDGED,
        "expected_version": 1,
    }
    values.update(overrides)
    return CalendarCommitmentResponse(**values)  # type: ignore[arg-type]


def test_a_subject_cannot_submit_a_pending_response() -> None:
    with pytest.raises(ValueError, match="cannot submit a pending response"):
        _response(state=CommitmentResponseState.PENDING)


def test_a_commitment_response_version_must_be_positive() -> None:
    with pytest.raises(ValueError, match="response version must be positive"):
        _response(expected_version=0)


def test_a_dispute_carries_a_reason_and_an_acknowledgement_does_not() -> None:
    disputed = _response(state=CommitmentResponseState.DISPUTED, reason="Already on leave.")

    assert disputed.reason == "Already on leave."
    with pytest.raises(ValueError, match="does not accept a reason"):
        _response(reason="Already on leave.")


def test_daily_recurrence_does_not_accept_weekdays() -> None:
    with pytest.raises(ValueError, match="daily recurrence does not accept weekdays"):
        CalendarRecurrence(CalendarFrequency.DAILY, 1, date(2026, 8, 20), weekdays=(1,))


def _occurrence() -> SimpleNamespace:
    return SimpleNamespace(occurrence_key="2026-08-06", timing=_timing())


def test_a_cancelled_occurrence_cannot_be_materialised() -> None:
    cancelled = CalendarOccurrenceException(occurrence_key="2026-08-06", cancelled=True)

    with pytest.raises(ValueError, match="cannot be materialised"):
        _apply_exception(_event(), _occurrence(), cancelled)  # type: ignore[arg-type]


def test_an_absent_exception_moves_the_event_onto_its_occurrence() -> None:
    occurrence = _occurrence()

    assert _apply_exception(_event(), occurrence, None).timing is occurrence.timing  # type: ignore[arg-type]


def test_an_exception_is_either_a_cancellation_or_a_complete_change() -> None:
    # The domain refuses a half-changed exception outright, so _apply_exception
    # never sees one; this is the guard that keeps it that way.
    with pytest.raises(ValueError, match="cancellation or complete change"):
        CalendarOccurrenceException(
            occurrence_key="2026-08-06",
            cancelled=False,
            timing=_timing(2),
            activity=None,
            availability=AvailabilityEffect.PARTIAL,
            privacy=CalendarPrivacy.PRIVATE,
            note="Synthetic exception",
        )


class _Users:
    def __init__(self, users: dict[UUID, SimpleNamespace]) -> None:
        self._users = users

    def get_user(self, user_id: UUID) -> SimpleNamespace | None:
        return self._users.get(user_id)


def test_only_the_subject_may_answer_their_own_commitment() -> None:
    service = WorkforceCalendarService(
        SimpleNamespace(),  # type: ignore[arg-type]
        _Users({OWNER: SimpleNamespace(is_active=True)}),  # type: ignore[arg-type]
        SimpleNamespace(),  # type: ignore[arg-type]
        clock=lambda: NOW,
    )

    with pytest.raises(CalendarMutationDenied, match="answered by their subject"):
        service.respond_to_commitment(OWNER, _response(subject_user_id=uuid4()))
