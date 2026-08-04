from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from organisation_account_support import activate_principals
from sqlalchemy import create_engine, text

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
    CalendarEventStatus,
    CalendarIdempotencyConflict,
    CalendarMutationCommand,
    CalendarMutationConflict,
    CalendarMutationDenied,
    CalendarMutationOperation,
    CalendarMutationRequest,
    CalendarPrivacy,
    CalendarTiming,
)
from coeus.persistence.organisation_postgres import PostgresOrganisationRepository
from coeus.persistence.workforce_calendar_postgres import (
    PostgresWorkforceCalendarStore,
    _mutate,
    _replay,
)
from coeus.services.workforce_calendar import WorkforceCalendarService

API_ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.postgres


class _Users:
    def __init__(self, *users: UserAccount) -> None:
        self._users = {user.user_id: user for user in users}

    def get_user(self, user_id: UUID) -> UserAccount | None:
        return self._users.get(user_id)


def _upgrade(database_url: str) -> None:
    config = Config(str(API_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "head")


def _fixture(
    database_url: str,
) -> tuple[
    object,
    WorkforceCalendarService,
    PostgresWorkforceCalendarStore,
    UUID,
    UUID,
    OrganisationManagementGrant,
    CalendarEvent,
]:
    _upgrade(database_url)
    engine = create_engine(database_url)
    repository = PostgresOrganisationRepository(engine)
    now = datetime.now(UTC)
    manager_id, owner_id = uuid4(), uuid4()
    activate_principals(engine, manager_id)
    unit = OrganisationUnit(
        uuid4(),
        "Calendar Branch Team",
        "CBT",
        OrganisationCategory.DELIVERY_TEAM,
        None,
        now - timedelta(days=1),
    )
    repository.upsert_unit(
        unit,
        OrganisationTopologyRevision(
            uuid4(), unit.unit_id, None, (unit.unit_id,), unit.valid_from, uuid4(), manager_id
        ),
    )
    repository.upsert_membership(
        TeamMembership(
            uuid4(),
            owner_id,
            unit.unit_id,
            MembershipRole.MEMBER,
            MembershipState.ACTIVE,
            True,
            now - timedelta(days=1),
            manager_id,
            "Calendar branch fixture.",
            "test",
        )
    )
    grant = OrganisationManagementGrant(
        uuid4(),
        manager_id,
        unit.unit_id,
        ManagementAction.CALENDAR_MANAGE,
        False,
        now - timedelta(days=1),
        manager_id,
        "Calendar branch fixture.",
    )
    repository.upsert_management_grant(grant)
    manager = UserAccount(
        manager_id,
        "calendar.branch.manager",
        "Branch Manager",
        frozenset(),
        frozenset(),
        "x",
        True,
        1,
    )
    owner = UserAccount(
        owner_id,
        "calendar.branch.owner",
        "Branch Owner",
        frozenset(),
        frozenset(),
        "x",
        True,
        1,
    )
    event = CalendarEvent(
        uuid4(),
        owner_id,
        CalendarEventSource.MANAGER,
        CalendarActivity.DUTY,
        CalendarTiming("UTC", now + timedelta(days=1), now + timedelta(days=1, hours=2)),
        AvailabilityEffect.PARTIAL,
        CalendarPrivacy.TEAM_SUMMARY,
        manager_id,
        manager_scope_unit_id=unit.unit_id,
    )
    store = PostgresWorkforceCalendarStore(engine)
    service = WorkforceCalendarService(repository, _Users(manager, owner), store, clock=lambda: now)
    return engine, service, store, manager_id, owner_id, grant, event


def _prepared_command(
    service: WorkforceCalendarService,
    manager_id: UUID,
    grant: OrganisationManagementGrant,
    event: CalendarEvent,
    *,
    key: str,
) -> CalendarMutationCommand:
    request = CalendarMutationRequest(
        CalendarMutationOperation.CREATE, event, 0, grant.grant_id, "Create branch fixture."
    )
    preview = service.preview(request, manager_id)
    return CalendarMutationCommand(uuid4(), key, manager_id, request, preview.preview_hash)


def test_manager_create_writes_home_scope_and_store_level_replay(
    postgres_database_url: str,
) -> None:
    engine, service, store, manager_id, _, grant, event = _fixture(postgres_database_url)
    command_record = _prepared_command(
        service, manager_id, grant, event, key="manager-create-branch"
    )
    assert service.execute(command_record).version == 1
    assert store.apply(command_record).replayed
    with engine.connect() as connection:  # type: ignore[union-attr]
        scopes = set(
            connection.execute(
                text("SELECT scope_type FROM calendar_event_scopes WHERE event_id=:event_id"),
                {"event_id": event.event_id},
            ).scalars()
        )
    assert scopes == {"owner_global", "home_unit"}
    engine.dispose()  # type: ignore[union-attr]


def test_final_boundary_rechecks_preview_hash_grant_and_membership(
    postgres_database_url: str,
) -> None:
    engine, service, store, manager_id, owner_id, grant, event = _fixture(postgres_database_url)
    stale = _prepared_command(service, manager_id, grant, event, key="stale-preview-branch")
    with pytest.raises(CalendarMutationConflict, match="preview is stale"):
        store.apply(replace(stale, preview_hash="f" * 64))
    revoked_event = replace(event, event_id=uuid4())
    revoked = _prepared_command(
        service, manager_id, grant, revoked_event, key="revoked-grant-branch"
    )
    with engine.begin() as connection:  # type: ignore[union-attr]
        connection.execute(
            text("UPDATE team_management_grants SET revoked_at=now() WHERE grant_id=:grant_id"),
            {"grant_id": grant.grant_id},
        )
    with pytest.raises(CalendarMutationDenied, match="management grant"):
        store.apply(revoked)
    with engine.begin() as connection:  # type: ignore[union-attr]
        connection.execute(
            text("UPDATE team_management_grants SET revoked_at=NULL WHERE grant_id=:grant_id"),
            {"grant_id": grant.grant_id},
        )
    moved_event = replace(event, event_id=uuid4())
    moved = _prepared_command(service, manager_id, grant, moved_event, key="moved-owner-branch")
    with engine.begin() as connection:  # type: ignore[union-attr]
        connection.execute(
            text("UPDATE team_memberships SET valid_until=now() WHERE user_id=:owner_id"),
            {"owner_id": owner_id},
        )
    with pytest.raises(CalendarMutationConflict, match="matching current home"):
        store.apply(moved)
    engine.dispose()  # type: ignore[union-attr]


def test_final_boundary_rejects_idempotency_and_lifecycle_collisions(
    postgres_database_url: str,
) -> None:
    engine, service, store, manager_id, _, grant, event = _fixture(postgres_database_url)
    original = _prepared_command(service, manager_id, grant, event, key="collision-branch")
    assert service.execute(original).version == 1
    with pytest.raises(CalendarIdempotencyConflict):
        store.replay(replace(original, command_id=uuid4()))
    with pytest.raises(CalendarIdempotencyConflict, match="different calendar operations"):
        _replay(({}, {}), original)  # type: ignore[arg-type]
    duplicate = replace(original, command_id=uuid4(), idempotency_key="duplicate-event-branch")
    with pytest.raises(CalendarMutationConflict, match="already exists"):
        store.apply(duplicate)
    unsupported = replace(
        original,
        command_id=uuid4(),
        idempotency_key="unsupported-source-branch",
        request=replace(
            original.request,
            event=replace(
                event,
                event_id=uuid4(),
                source=CalendarEventSource.TASK,
                manager_scope_unit_id=None,
            ),
            authorising_grant_id=None,
        ),
    )
    with pytest.raises(CalendarMutationDenied, match="separate authority"):
        store.apply(unsupported)
    personal = replace(
        unsupported,
        command_id=uuid4(),
        idempotency_key="wrong-personal-owner-branch",
        request=replace(
            unsupported.request,
            event=replace(
                unsupported.request.event,
                event_id=uuid4(),
                source=CalendarEventSource.PERSONAL,
                created_by_user_id=manager_id,
            ),
        ),
    )
    with pytest.raises(CalendarMutationDenied, match="owner-managed"):
        store.apply(personal)

    def command_for(request: CalendarMutationRequest, key: str) -> CalendarMutationCommand:
        return CalendarMutationCommand(uuid4(), key, manager_id, request, "e" * 64)

    bad_create = replace(
        original.request,
        event=replace(event, event_id=uuid4(), created_by_user_id=uuid4()),
    )
    with pytest.raises(CalendarMutationConflict, match="metadata"):
        store.apply(command_for(bad_create, "bad-create-metadata-branch"))
    missing_update = CalendarMutationRequest(
        CalendarMutationOperation.UPDATE,
        replace(event, event_id=uuid4()),
        1,
        grant.grant_id,
        "Update missing fixture.",
    )
    with pytest.raises(CalendarMutationConflict, match="does not exist"):
        store.apply(command_for(missing_update, "missing-update-branch"))
    stale_identity = CalendarMutationRequest(
        CalendarMutationOperation.UPDATE,
        replace(event, owner_user_id=uuid4()),
        1,
        grant.grant_id,
        "Change immutable fixture.",
    )
    with pytest.raises(CalendarMutationConflict, match="identity or version"):
        store.apply(command_for(stale_identity, "stale-identity-branch"))
    cancelled_update = CalendarMutationRequest(
        CalendarMutationOperation.UPDATE,
        replace(event, status=CalendarEventStatus.CANCELLED, cancelled_at=datetime.now(UTC)),
        1,
        grant.grant_id,
        "Submit cancelled update.",
    )
    with pytest.raises(CalendarMutationConflict, match="active event"):
        store.apply(command_for(cancelled_update, "cancelled-update-branch"))
    engine.dispose()  # type: ignore[union-attr]


@pytest.mark.parametrize(
    "operation", (CalendarMutationOperation.CREATE, CalendarMutationOperation.UPDATE)
)
def test_mutation_detects_a_lost_write(operation: CalendarMutationOperation) -> None:
    class _NoWriteResult:
        @staticmethod
        def scalar_one_or_none() -> None:
            return None

    class _NoWriteConnection:
        @staticmethod
        def execute(statement: object, params: object) -> _NoWriteResult:
            del statement, params
            return _NoWriteResult()

    manager_id, owner_id, unit_id = uuid4(), uuid4(), uuid4()
    event = CalendarEvent(
        uuid4(),
        owner_id,
        CalendarEventSource.MANAGER,
        CalendarActivity.DUTY,
        CalendarTiming("UTC", datetime.now(UTC), datetime.now(UTC) + timedelta(hours=1)),
        AvailabilityEffect.PARTIAL,
        CalendarPrivacy.TEAM_SUMMARY,
        manager_id,
        manager_scope_unit_id=unit_id,
    )
    request = CalendarMutationRequest(
        operation,
        event,
        0 if operation.value == "create" else 1,
        uuid4(),
        "Lost write.",
    )
    command_record = CalendarMutationCommand(
        uuid4(), f"lost-{operation}", manager_id, request, "a" * 64
    )
    with pytest.raises(CalendarMutationConflict, match="identity or version"):
        _mutate(_NoWriteConnection(), command_record, datetime.now(UTC))  # type: ignore[arg-type]
