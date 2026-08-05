"""Window bounds and owner-account checks around calendar mutations."""

from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from coeus.domain.workforce_calendar import (
    AvailabilityEffect,
    CalendarActivity,
    CalendarEvent,
    CalendarEventSource,
    CalendarFrequency,
    CalendarMutationConflict,
    CalendarPrivacy,
    CalendarRecurrence,
    CalendarTiming,
)
from coeus.services.workforce_calendar import WorkforceCalendarService

NOW = datetime(2026, 8, 4, 12, tzinfo=UTC)
OWNER = uuid4()


class _Users:
    def __init__(self, users: dict[UUID, SimpleNamespace]) -> None:
        self._users = users

    def get_user(self, user_id: UUID) -> SimpleNamespace | None:
        return self._users.get(user_id)


def _service(users: dict[UUID, SimpleNamespace] | None = None) -> WorkforceCalendarService:
    return WorkforceCalendarService(
        SimpleNamespace(),  # type: ignore[arg-type]
        _Users(users if users is not None else {OWNER: SimpleNamespace(is_active=True)}),  # type: ignore[arg-type]
        SimpleNamespace(),  # type: ignore[arg-type]
        clock=lambda: NOW,
    )


def _event(**overrides: object) -> CalendarEvent:
    values: dict[str, object] = {
        "event_id": uuid4(),
        "owner_user_id": OWNER,
        "source": CalendarEventSource.PERSONAL,
        "activity": CalendarActivity.TRAINING,
        "timing": CalendarTiming(
            "Europe/London",
            starts_at=NOW + timedelta(days=1),
            ends_at=NOW + timedelta(days=1, hours=1),
        ),
        "availability": AvailabilityEffect.PARTIAL,
        "privacy": CalendarPrivacy.PRIVATE,
        "created_by_user_id": OWNER,
    }
    values.update(overrides)
    return CalendarEvent(**values)  # type: ignore[arg-type]


def test_a_personal_window_must_run_forward_and_stay_within_a_year() -> None:
    service = _service()

    with pytest.raises(ValueError, match="window end must follow its start"):
        service.personal_calendar(OWNER, NOW, NOW)
    with pytest.raises(ValueError, match="cannot exceed 366 days"):
        service.personal_calendar(OWNER, NOW, NOW + timedelta(days=367))


@pytest.mark.parametrize(
    "users",
    [{}, {OWNER: SimpleNamespace(is_active=False)}],
)
def test_an_unknown_or_closed_owner_account_blocks_commitments(
    users: dict[UUID, SimpleNamespace],
) -> None:
    service = _service(users)

    with pytest.raises(CalendarMutationConflict, match="owner account is not active"):
        service.commitments(OWNER)


def test_a_timed_event_must_end_in_the_future() -> None:
    past = CalendarTiming(
        "Europe/London",
        starts_at=NOW - timedelta(days=2),
        ends_at=NOW - timedelta(days=1),
    )

    WorkforceCalendarService._validate_window(_event(), NOW)
    with pytest.raises(CalendarMutationConflict, match="must end in the future"):
        WorkforceCalendarService._validate_window(_event(timing=past), NOW)


def test_an_all_day_event_must_end_in_the_future() -> None:
    past = CalendarTiming(
        "Europe/London",
        all_day_start=NOW.date() - timedelta(days=3),
        all_day_end=NOW.date() - timedelta(days=1),
    )
    future = CalendarTiming(
        "Europe/London",
        all_day_start=NOW.date() + timedelta(days=1),
        all_day_end=NOW.date() + timedelta(days=2),
    )

    WorkforceCalendarService._validate_window(_event(timing=future), NOW)
    with pytest.raises(CalendarMutationConflict, match="must end in the future"):
        WorkforceCalendarService._validate_window(_event(timing=past), NOW)


def test_a_past_seed_is_accepted_while_its_recurrence_still_runs() -> None:
    past = CalendarTiming(
        "Europe/London",
        starts_at=NOW - timedelta(days=2),
        ends_at=NOW - timedelta(days=2) + timedelta(hours=1),
    )
    recurrence = CalendarRecurrence(CalendarFrequency.DAILY, 1, date(2026, 8, 20))

    WorkforceCalendarService._validate_window(_event(timing=past, recurrence=recurrence), NOW)
