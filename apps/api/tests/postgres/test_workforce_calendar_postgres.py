"""Real PostgreSQL evidence for canonical personal calendar commands."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from organisation_account_support import activate_principals
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError

from coeus.domain.auth import UserAccount
from coeus.domain.organisation import (
    ManagementAction,
    MembershipRole,
    MembershipState,
    OrganisationCategory,
    OrganisationManagementGrant,
    OrganisationTopologyRevision,
    OrganisationUnit,
    TeamMembership,
)
from coeus.domain.workforce_calendar import (
    AvailabilityEffect,
    CalendarActivity,
    CalendarEvent,
    CalendarEventSource,
    CalendarIdempotencyConflict,
    CalendarMutationCommand,
    CalendarMutationOperation,
    CalendarMutationRequest,
    CalendarMutationResult,
    CalendarPrivacy,
    CalendarProjectionDenied,
    CalendarTiming,
)
from coeus.persistence.organisation_postgres import PostgresOrganisationRepository
from coeus.persistence.workforce_calendar_postgres import PostgresWorkforceCalendarStore
from coeus.services.workforce_calendar import WorkforceCalendarService

API_ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.postgres


class _Users:
    def __init__(self, *users: UserAccount) -> None:
        self.users = {user.user_id: user for user in users}

    def get_user(self, user_id: UUID) -> UserAccount | None:
        return self.users.get(user_id)


def _upgrade(database_url: str) -> None:
    config = Config(str(API_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "head")


def _request(
    event: CalendarEvent, operation: CalendarMutationOperation, version: int, reason: str
) -> CalendarMutationRequest:
    return CalendarMutationRequest(operation, event, version, None, reason)


def _execute(
    service: WorkforceCalendarService,
    actor_id: UUID,
    request: CalendarMutationRequest,
    key: str,
) -> tuple[CalendarMutationResult, CalendarMutationCommand]:
    preview = service.preview(request, actor_id)
    command_record = CalendarMutationCommand(uuid4(), key, actor_id, request, preview.preview_hash)
    return service.execute(command_record), command_record


def test_personal_event_lifecycle_is_versioned_idempotent_and_tombstoned(
    postgres_database_url: str,
) -> None:
    _upgrade(postgres_database_url)
    engine = create_engine(postgres_database_url)
    actor_id = uuid4()
    user = UserAccount(
        actor_id,
        "calendar.user",
        "Calendar User",
        frozenset(),
        frozenset(),
        "x",
        True,
        1,
    )
    now = datetime.now(UTC)
    store = PostgresWorkforceCalendarStore(engine)
    service = WorkforceCalendarService(
        PostgresOrganisationRepository(engine), _Users(user), store, clock=lambda: now
    )
    event = CalendarEvent(
        uuid4(),
        actor_id,
        CalendarEventSource.PERSONAL,
        CalendarActivity.TRAINING,
        CalendarTiming("Europe/London", now + timedelta(days=2), now + timedelta(days=2, hours=2)),
        AvailabilityEffect.PARTIAL,
        CalendarPrivacy.TEAM_SUMMARY,
        actor_id,
        "Sensitive synthetic course detail.",
    )
    created, create_command = _execute(
        service,
        actor_id,
        _request(event, CalendarMutationOperation.CREATE, 0, "Create training."),
        "create-training",
    )
    assert created.version == 1
    assert service.execute(create_command).replayed

    changed_event = replace(
        event,
        activity=CalendarActivity.DUTY,
        note="Sensitive synthetic duty detail.",
        version=1,
    )
    changed, _ = _execute(
        service,
        actor_id,
        _request(changed_event, CalendarMutationOperation.UPDATE, 1, "Change duty."),
        "update-training",
    )
    assert changed.version == 2
    stored = store.get_event(event.event_id)
    assert stored is not None and stored.activity is CalendarActivity.DUTY

    cancelled, _ = _execute(
        service,
        actor_id,
        _request(stored, CalendarMutationOperation.CANCEL, 2, "Cancel duty."),
        "cancel-training",
    )
    assert cancelled.version == 3
    assert store.list_owner_events(actor_id, now, now + timedelta(days=10)) == ()

    with engine.connect() as connection:
        assert (
            connection.execute(text("SELECT count(*) FROM calendar_event_versions")).scalar_one()
            == 3
        )
        evidence = " ".join(
            connection.execute(
                text(
                    "SELECT metadata::text FROM coeus_audit_events "
                    "WHERE event_type LIKE 'calendar_event_%'"
                )
            ).scalars()
        )
        assert "Sensitive synthetic" not in evidence
        with pytest.raises(DBAPIError, match="cancelled, not deleted"):
            connection.execute(
                text("DELETE FROM calendar_events WHERE event_id=:event_id"),
                {"event_id": event.event_id},
            )
    engine.dispose()


def test_actor_bound_idempotency_key_rejects_a_different_command(
    postgres_database_url: str,
) -> None:
    _upgrade(postgres_database_url)
    engine = create_engine(postgres_database_url)
    actor_id = uuid4()
    user = UserAccount(
        actor_id, "calendar.user", "Calendar User", frozenset(), frozenset(), "x", True, 1
    )
    now = datetime.now(UTC)
    store = PostgresWorkforceCalendarStore(engine)
    service = WorkforceCalendarService(
        PostgresOrganisationRepository(engine), _Users(user), store, clock=lambda: now
    )
    event = CalendarEvent(
        uuid4(),
        actor_id,
        CalendarEventSource.PERSONAL,
        CalendarActivity.LEAVE,
        CalendarTiming("UTC", now + timedelta(days=1), now + timedelta(days=2)),
        AvailabilityEffect.UNAVAILABLE,
        CalendarPrivacy.PRIVATE,
        actor_id,
    )
    request = _request(event, CalendarMutationOperation.CREATE, 0, "Create leave.")
    _, first = _execute(service, actor_id, request, "same-key")
    with pytest.raises(CalendarIdempotencyConflict):
        service.execute(replace(first, command_id=uuid4()))
    engine.dispose()


def test_projection_revalidates_exact_grant_lineage_and_current_membership(
    postgres_database_url: str,
) -> None:
    _upgrade(postgres_database_url)
    engine = create_engine(postgres_database_url)
    organisation = PostgresOrganisationRepository(engine)
    now = datetime.now(UTC)
    manager_id, owner_id = uuid4(), uuid4()
    activate_principals(engine, manager_id)
    root = OrganisationUnit(
        uuid4(),
        "Synthetic Command",
        "SYN-CMD",
        OrganisationCategory.COMMAND,
        None,
        now - timedelta(days=1),
    )
    child = OrganisationUnit(
        uuid4(),
        "Synthetic Analysis Team",
        "SYN-AT",
        OrganisationCategory.DELIVERY_TEAM,
        root.unit_id,
        now - timedelta(days=1),
    )
    organisation.upsert_unit(
        root,
        OrganisationTopologyRevision(
            uuid4(), root.unit_id, None, (root.unit_id,), root.valid_from, uuid4(), manager_id
        ),
    )
    organisation.upsert_unit(
        child,
        OrganisationTopologyRevision(
            uuid4(),
            child.unit_id,
            root.unit_id,
            (root.unit_id, child.unit_id),
            child.valid_from,
            uuid4(),
            manager_id,
        ),
    )
    organisation.upsert_membership(
        TeamMembership(
            uuid4(),
            owner_id,
            child.unit_id,
            MembershipRole.MEMBER,
            MembershipState.ACTIVE,
            True,
            now - timedelta(days=1),
            manager_id,
            "Synthetic team posting.",
            "test",
        )
    )
    grant = OrganisationManagementGrant(
        uuid4(),
        manager_id,
        root.unit_id,
        ManagementAction.CALENDAR_VIEW_AVAILABILITY,
        True,
        now - timedelta(days=1),
        manager_id,
        "Synthetic calendar authority.",
    )
    organisation.upsert_management_grant(grant)
    manager = UserAccount(
        manager_id, "calendar.manager", "Calendar Manager", frozenset(), frozenset(), "x", True, 1
    )
    owner = UserAccount(
        owner_id, "calendar.owner", "Calendar Owner", frozenset(), frozenset(), "x", True, 1
    )
    store = PostgresWorkforceCalendarStore(engine)
    service = WorkforceCalendarService(
        organisation, _Users(manager, owner), store, clock=lambda: now
    )
    event = CalendarEvent(
        uuid4(),
        owner_id,
        CalendarEventSource.PERSONAL,
        CalendarActivity.TRAINING,
        CalendarTiming("Europe/London", now + timedelta(days=1), now + timedelta(days=2)),
        AvailabilityEffect.UNAVAILABLE,
        CalendarPrivacy.PRIVATE,
        owner_id,
        "Sensitive synthetic event.",
    )
    _execute(
        service,
        owner_id,
        _request(event, CalendarMutationOperation.CREATE, 0, "Create synthetic event."),
        "create-projection-event",
    )

    direct = service.team_projection(manager_id, child.unit_id, now, now + timedelta(days=7))
    assert direct.member_count == 1 and len(direct.entries) == 1
    assert direct.entries[0].owner_user_id is None and direct.entries[0].note is None
    descendant = service.team_projection(
        manager_id,
        root.unit_id,
        now,
        now + timedelta(days=7),
        include_descendants=True,
    )
    assert descendant.suppressed and descendant.entries == ()

    with pytest.raises(CalendarProjectionDenied):
        store.list_unit_events(
            manager_id,
            grant.grant_id,
            ManagementAction.CALENDAR_VIEW_DETAIL,
            root.unit_id,
            (root.unit_id, child.unit_id),
            now,
            now + timedelta(days=7),
        )
    engine.dispose()
