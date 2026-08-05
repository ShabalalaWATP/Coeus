"""Real PostgreSQL regressions for suspended package owners.

Suspending an account is reconciled by the database itself: the person is
released from every open package and their held capacity is freed. These tests
prove that reconciliation happens and that the planning commands still refuse to
act on the evidence they were built from.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, text

from coeus.domain.synthetic_organisation_fixture import (
    SyntheticFixtureCommand,
    SyntheticFixtureUser,
)
from coeus.domain.work_package_planning import (
    PlanWorkPackageCommand,
    WorkPackagePlanningConflict,
    WorkPackagePlanningDenied,
    WorkPackagePlanRequest,
)
from coeus.domain.work_packages import CapacityReservationConflict, ReserveCapacityCommand
from coeus.persistence.capacity_reservations_postgres import PostgresCapacityReservationStore
from coeus.persistence.synthetic_organisation_fixture_postgres import (
    PostgresSyntheticOrganisationFixtureStore,
)
from coeus.persistence.work_package_planning_postgres import PostgresWorkPackagePlanningStore
from coeus.repositories.auth_seed import seed_user_specs
from coeus.repositories.synthetic_organisation_manifest import (
    synthetic_posting_specs,
    synthetic_unit_specs,
)
from coeus.repositories.synthetic_task_manifest import synthetic_task_specs
from coeus.repositories.synthetic_workforce import synthetic_user_id

API_ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.postgres


@dataclass(frozen=True)
class _PlanningContext:
    engine: Engine
    actor_id: UUID
    owner_id: UUID
    request: WorkPackagePlanRequest


def _context(database_url: str) -> _PlanningContext:
    config = Config(str(API_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "head")
    engine = create_engine(database_url)
    active = {item.username: item.is_active for item in seed_user_specs()}
    users = tuple(
        SyntheticFixtureUser(
            username,
            synthetic_user_id(username),
            active[username],
        )
        for username in dict.fromkeys(item.username for item in synthetic_posting_specs())
    )
    actor_id = synthetic_user_id("admin@example.test")
    fixture = PostgresSyntheticOrganisationFixtureStore(engine)
    preview = fixture.preview(actor_id, users)
    fixture.apply(
        SyntheticFixtureCommand(
            uuid4(), "planning-account-guard-fixture", actor_id, preview.preview_hash
        ),
        users,
    )
    _project_accounts(engine, users)
    task = next(item for item in synthetic_task_specs() if item.key == "mar-2")
    unit_id = next(item.unit_id for item in synthetic_unit_specs() if item.key == task.unit_key)
    manager_id = synthetic_user_id(task.manager_username)
    owner_id = synthetic_user_id(task.assignee_username or "")
    with engine.connect() as connection:
        grant_id = connection.execute(
            text(
                "SELECT grant_id FROM team_management_grants "
                "WHERE manager_user_id=:manager_id AND root_unit_id=:unit_id "
                "AND action='task:assign' AND revoked_at IS NULL LIMIT 1"
            ),
            {"manager_id": manager_id, "unit_id": unit_id},
        ).scalar_one()
    request = WorkPackagePlanRequest(
        unit_id,
        task.package_id(1),
        1,
        1,
        owner_id,
        240,
        180,
        datetime(2026, 8, 18, 17, tzinfo=UTC),
        2,
        "Synthetic deadline priority.",
        uuid4(),
        datetime(2026, 8, 17, 8, tzinfo=UTC),
        datetime(2026, 8, 17, 12, tzinfo=UTC),
        60,
        grant_id,
    )
    return _PlanningContext(engine, manager_id, owner_id, request)


def _project_accounts(engine: Engine, users: tuple[SyntheticFixtureUser, ...]) -> None:
    analyst_ids = {
        synthetic_user_id(item.username)
        for item in synthetic_posting_specs()
        if item.assignment_eligible or item.username.startswith("analyst")
    }
    with engine.begin() as connection:
        for user in users:
            connection.execute(
                text(
                    "INSERT INTO identity_account_projection"
                    "(user_id,is_active,roles,credential_version,source_hash) "
                    "VALUES (:user_id,:active,:roles,0,:source_hash)"
                ),
                {
                    "user_id": user.user_id,
                    "active": user.is_active,
                    "roles": ["Analyst"] if user.user_id in analyst_ids else [],
                    "source_hash": "0" * 64,
                },
            )


def _suspend(context: _PlanningContext, credential_version: int) -> None:
    with context.engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE identity_account_projection SET is_active=false,"
                "credential_version=:version,source_hash=:source_hash WHERE user_id=:user_id"
            ),
            {
                "user_id": context.owner_id,
                "version": credential_version,
                "source_hash": f"{credential_version:x}" * 64,
            },
        )


def _state(context: _PlanningContext) -> tuple[object, ...]:
    with context.engine.connect() as connection:
        return tuple(
            connection.execute(
                text(
                    "SELECT package.version,package.estimated_minutes,package.remaining_minutes,"
                    "(SELECT count(*) FROM capacity_reservations r "
                    "WHERE r.package_id=package.package_id),"
                    "(SELECT count(*) FROM work_package_history h "
                    "WHERE h.package_id=package.package_id),"
                    "(SELECT count(*) FROM work_package_commands c "
                    "WHERE c.package_id=package.package_id) "
                    "FROM canonical_work_packages package WHERE package.package_id=:package_id"
                ),
                {"package_id": context.request.package_id},
            ).one()
        )


def _assert_membership_remains_active(context: _PlanningContext) -> None:
    with context.engine.connect() as connection:
        assert (
            connection.execute(
                text(
                    "SELECT count(*) FROM team_memberships WHERE user_id=:user_id "
                    "AND unit_id=:unit_id AND state='active' AND assignment_eligible"
                ),
                {"user_id": context.owner_id, "unit_id": context.request.unit_id},
            ).scalar_one()
            == 1
        )


def _released_package(context: _PlanningContext) -> tuple[object, ...]:
    with context.engine.connect() as connection:
        return tuple(
            connection.execute(
                text(
                    "SELECT state,accountable_user_id,version FROM canonical_work_packages "
                    "WHERE package_id=:package_id"
                ),
                {"package_id": context.request.package_id},
            ).one()
        )


def _live_reservation_count(context: _PlanningContext) -> int:
    with context.engine.connect() as connection:
        return int(
            connection.execute(
                text(
                    "SELECT count(*) FROM capacity_reservations "
                    "WHERE user_id=:user_id AND state IN ('held','active')"
                ),
                {"user_id": context.owner_id},
            ).scalar_one()
        )


def test_suspension_releases_the_package_and_refuses_stale_planning(
    postgres_database_url: str,
) -> None:
    context = _context(postgres_database_url)
    before = _state(context)
    _suspend(context, 1)
    _assert_membership_remains_active(context)

    state, accountable, version = _released_package(context)
    assert state == "pending"
    assert accountable is None
    assert version == int(str(before[0])) + 1
    assert _live_reservation_count(context) == 0
    reconciled = _state(context)

    with pytest.raises(WorkPackagePlanningConflict, match="evidence changed"):
        PostgresWorkPackagePlanningStore(context.engine).preview(context.actor_id, context.request)

    assert _state(context) == reconciled
    context.engine.dispose()


def test_execute_refuses_evidence_invalidated_by_suspension_and_rolls_back(
    postgres_database_url: str,
) -> None:
    context = _context(postgres_database_url)
    planner = PostgresWorkPackagePlanningStore(context.engine)
    preview = planner.preview(context.actor_id, context.request)
    command_to_execute = PlanWorkPackageCommand(
        uuid4(), "suspended-owner-plan", context.actor_id, context.request, preview.preview_hash
    )
    _suspend(context, 1)
    _assert_membership_remains_active(context)
    reconciled = _state(context)

    with pytest.raises(WorkPackagePlanningConflict, match="evidence changed"):
        planner.execute(command_to_execute)

    assert _state(context) == reconciled
    context.engine.dispose()


def test_replay_denies_owner_suspended_after_success_without_new_evidence(
    postgres_database_url: str,
) -> None:
    context = _context(postgres_database_url)
    planner = PostgresWorkPackagePlanningStore(context.engine)
    preview = planner.preview(context.actor_id, context.request)
    planning_command = PlanWorkPackageCommand(
        uuid4(), "suspended-owner-replay", context.actor_id, context.request, preview.preview_hash
    )
    result = planner.execute(planning_command)
    assert not result.replayed
    _suspend(context, 1)
    _assert_membership_remains_active(context)
    reconciled = _state(context)

    # The stored result is never replayed back to a person who no longer holds
    # the package: the replay path revalidates current scope.
    with pytest.raises(WorkPackagePlanningDenied, match="planning authority"):
        planner.execute(planning_command)

    assert _state(context) == reconciled
    context.engine.dispose()


def test_direct_reservation_refuses_a_package_released_by_suspension(
    postgres_database_url: str,
) -> None:
    context = _context(postgres_database_url)
    request = context.request
    task = next(item for item in synthetic_task_specs() if item.package_id(1) == request.package_id)
    direct = ReserveCapacityCommand(
        request.reservation_id,
        context.actor_id,
        context.owner_id,
        task.ticket_id,
        task.workflow_leg,
        request.package_id,
        request.starts_at,
        request.ends_at,
        request.reserved_minutes,
        "suspended-owner-direct-reservation",
        request.expected_package_version,
    )
    _suspend(context, 1)
    _assert_membership_remains_active(context)
    reconciled = _state(context)

    # Reconciliation returns the package to 'pending', which is outside the set
    # of states that can hold capacity at all.
    with pytest.raises(CapacityReservationConflict, match="work package is unavailable"):
        PostgresCapacityReservationStore(postgres_database_url).reserve(direct)

    assert _state(context) == reconciled
    context.engine.dispose()
