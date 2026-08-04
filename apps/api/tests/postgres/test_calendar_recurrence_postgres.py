"""Real PostgreSQL proof for recurring calendar read selection and integrity."""

from dataclasses import replace
from datetime import UTC, date, datetime
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

from coeus.domain.auth import UserAccount
from coeus.domain.workforce_calendar import (
    AvailabilityEffect,
    CalendarActivity,
    CalendarEvent,
    CalendarEventSource,
    CalendarFrequency,
    CalendarMutationCommand,
    CalendarMutationOperation,
    CalendarMutationRequest,
    CalendarMutationResult,
    CalendarPrivacy,
    CalendarRecurrence,
    CalendarTiming,
)
from coeus.persistence.calendar_capacity_expansion import capacity_intervals
from coeus.persistence.capacity_reservation_sql import CALENDAR
from coeus.persistence.organisation_postgres import PostgresOrganisationRepository
from coeus.persistence.workforce_calendar_postgres import PostgresWorkforceCalendarStore
from coeus.services.workforce_calendar import WorkforceCalendarService

pytestmark = pytest.mark.postgres
API_ROOT = Path(__file__).resolve().parents[2]


class _Users:
    def __init__(self, user: UserAccount) -> None:
        self.user = user

    def get_user(self, user_id: UUID) -> UserAccount | None:
        return self.user if user_id == self.user.user_id else None


def test_seed_before_window_expands_and_safe_exceptions_are_applied(
    postgres_database_url: str,
) -> None:
    config = Config(str(API_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", postgres_database_url)
    command.upgrade(config, "head")
    engine = create_engine(postgres_database_url)
    actor_id = uuid4()
    user = UserAccount(
        actor_id, "series.user", "Series User", frozenset(), frozenset(), "x", True, 1
    )
    now = datetime(2026, 3, 1, tzinfo=UTC)
    store = PostgresWorkforceCalendarStore(engine)
    service = WorkforceCalendarService(
        PostgresOrganisationRepository(engine), _Users(user), store, clock=lambda: now
    )
    event = CalendarEvent(
        uuid4(),
        actor_id,
        CalendarEventSource.PERSONAL,
        CalendarActivity.TRAINING,
        CalendarTiming(
            "Europe/London",
            datetime(2026, 3, 27, 9, tzinfo=UTC),
            datetime(2026, 3, 27, 10, tzinfo=UTC),
        ),
        AvailabilityEffect.UNAVAILABLE,
        CalendarPrivacy.TEAM_SUMMARY,
        actor_id,
        recurrence=CalendarRecurrence(CalendarFrequency.DAILY, 1, date(2026, 3, 30)),
    )
    request = CalendarMutationRequest(
        CalendarMutationOperation.CREATE, event, 0, None, "Create daily series."
    )
    preview = service.preview(request, actor_id)
    service.execute(
        CalendarMutationCommand(
            uuid4(), "create-daily-series", actor_id, request, preview.preview_hash
        )
    )
    occurrences = service.personal_calendar(
        actor_id, datetime(2026, 3, 29, tzinfo=UTC), datetime(2026, 3, 31, tzinfo=UTC)
    )
    assert [item.occurrence_key for item in occurrences] == ["2026-03-29", "2026-03-30"]
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO calendar_event_exceptions(exception_id,event_id,occurrence_key,"
                "action,created_by_user_id) VALUES (:id,:event_id,'2026-03-30','cancel',:actor)"
            ),
            {"id": uuid4(), "event_id": event.event_id, "actor": actor_id},
        )
    remaining = service.personal_calendar(
        actor_id, datetime(2026, 3, 29, tzinfo=UTC), datetime(2026, 3, 31, tzinfo=UTC)
    )
    assert [item.occurrence_key for item in remaining] == ["2026-03-29"]
    with engine.begin() as connection:
        rows = tuple(
            connection.execute(
                text(CALENDAR),
                {
                    "user_id": actor_id,
                    "start": datetime(2026, 3, 29, tzinfo=UTC),
                    "end": datetime(2026, 3, 31, tzinfo=UTC),
                },
            ).mappings()
        )
        assert len(rows) == 1
        blocked = capacity_intervals(
            dict(rows[0]),
            datetime(2026, 3, 29, tzinfo=UTC),
            datetime(2026, 3, 31, tzinfo=UTC),
        )
    assert len(blocked) == 1
    engine.dispose()


def test_owner_can_cancel_one_change_one_and_split_future_occurrences(
    postgres_database_url: str,
) -> None:
    config = Config(str(API_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", postgres_database_url)
    command.upgrade(config, "head")
    engine = create_engine(postgres_database_url)
    actor_id = uuid4()
    user = UserAccount(
        actor_id, "occurrence.user", "Occurrence User", frozenset(), frozenset(), "x", True, 1
    )
    store = PostgresWorkforceCalendarStore(engine)
    service = WorkforceCalendarService(
        PostgresOrganisationRepository(engine),
        _Users(user),
        store,
        clock=lambda: datetime(2026, 3, 1, tzinfo=UTC),
    )
    event = CalendarEvent(
        uuid4(),
        actor_id,
        CalendarEventSource.PERSONAL,
        CalendarActivity.TRAINING,
        CalendarTiming(
            "Europe/London", all_day_start=date(2026, 3, 27), all_day_end=date(2026, 3, 28)
        ),
        AvailabilityEffect.UNAVAILABLE,
        CalendarPrivacy.TEAM_SUMMARY,
        actor_id,
        recurrence=CalendarRecurrence(CalendarFrequency.DAILY, 1, date(2026, 3, 31)),
    )
    _execute(service, actor_id, CalendarMutationOperation.CREATE, event, 0, "create", None)
    cancelled = _execute(
        service,
        actor_id,
        CalendarMutationOperation.CANCEL_OCCURRENCE,
        replace(event, version=1),
        1,
        "cancel-one",
        "2026-03-28",
    )
    changed_event = replace(
        event,
        version=cancelled.version,
        activity=CalendarActivity.DUTY,
        availability=AvailabilityEffect.AVAILABLE,
        timing=CalendarTiming(
            "Europe/London",
            datetime(2026, 3, 29, 12, tzinfo=UTC),
            datetime(2026, 3, 29, 14, tzinfo=UTC),
        ),
        note="Short duty",
    )
    changed = _execute(
        service,
        actor_id,
        CalendarMutationOperation.UPDATE_OCCURRENCE,
        changed_event,
        cancelled.version,
        "change-one",
        "2026-03-29",
    )
    with engine.begin() as connection:
        changed_rows = tuple(
            connection.execute(
                text(CALENDAR),
                {
                    "user_id": actor_id,
                    "start": datetime(2026, 3, 29, tzinfo=UTC),
                    "end": datetime(2026, 3, 29, 22, tzinfo=UTC),
                },
            ).mappings()
        )
    assert len(changed_rows) == 1
    assert (
        capacity_intervals(
            dict(changed_rows[0]),
            datetime(2026, 3, 29, tzinfo=UTC),
            datetime(2026, 3, 29, 22, tzinfo=UTC),
        )
        == ()
    )
    future_id = uuid4()
    future_event = replace(
        event,
        version=changed.version,
        timing=CalendarTiming(
            "Europe/London", all_day_start=date(2026, 3, 30), all_day_end=date(2026, 3, 31)
        ),
        activity=CalendarActivity.LEAVE,
    )
    split = _execute(
        service,
        actor_id,
        CalendarMutationOperation.UPDATE_FUTURE,
        future_event,
        changed.version,
        "split-future",
        "2026-03-30",
        future_id,
    )
    assert split.future_event_id == future_id
    occurrences = service.personal_calendar(
        actor_id, datetime(2026, 3, 27, tzinfo=UTC), datetime(2026, 4, 1, tzinfo=UTC)
    )
    assert [(item.occurrence_key, item.event.activity) for item in occurrences] == [
        ("2026-03-27", CalendarActivity.TRAINING),
        ("2026-03-29", CalendarActivity.DUTY),
        ("2026-03-30", CalendarActivity.LEAVE),
        ("2026-03-31", CalendarActivity.LEAVE),
    ]
    assert occurrences[1].event.timing.starts_at == datetime(2026, 3, 29, 12, tzinfo=UTC)
    engine.dispose()


def _execute(
    service: WorkforceCalendarService,
    actor_id: UUID,
    operation: CalendarMutationOperation,
    event: CalendarEvent,
    version: int,
    key: str,
    occurrence_key: str | None,
    future_event_id: UUID | None = None,
) -> CalendarMutationResult:
    request = CalendarMutationRequest(
        operation,
        event,
        version,
        None,
        "Synthetic occurrence action.",
        occurrence_key,
        future_event_id,
    )
    preview = service.preview(request, actor_id)
    return service.execute(
        CalendarMutationCommand(uuid4(), key, actor_id, request, preview.preview_hash)
    )
