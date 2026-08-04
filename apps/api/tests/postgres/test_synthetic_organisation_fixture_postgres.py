"""Real PostgreSQL evidence for the atomic synthetic organisation fixture."""

from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from synthetic_fixture_projection_support import assert_fixture_projections

from coeus.domain.organisation import ManagementAction
from coeus.domain.synthetic_organisation_fixture import (
    SyntheticFixtureCommand,
    SyntheticFixtureConflict,
    SyntheticFixtureUser,
)
from coeus.domain.work_package_planning import PlanWorkPackageCommand, WorkPackagePlanRequest
from coeus.domain.work_packages import (
    CapacityAuthorityDenied,
    CapacityReservationConflict,
    ReserveCapacityCommand,
)
from coeus.persistence.capacity_reservations_postgres import PostgresCapacityReservationStore
from coeus.persistence.synthetic_organisation_fixture_postgres import (
    PostgresSyntheticOrganisationFixtureStore,
)
from coeus.persistence.work_package_planning_postgres import (
    PostgresWorkPackagePlanningStore,
)
from coeus.repositories.auth_seed import seed_user_specs
from coeus.repositories.synthetic_grant_manifest import (
    synthetic_management_grants,
    synthetic_service_grants,
)
from coeus.repositories.synthetic_organisation_manifest import (
    synthetic_posting_specs,
    synthetic_unit_specs,
)
from coeus.repositories.synthetic_task_manifest import synthetic_task_specs
from coeus.repositories.synthetic_workforce import synthetic_user_id

API_ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.postgres


def _upgrade(database_url: str) -> None:
    config = Config(str(API_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "head")


def _users() -> tuple[SyntheticFixtureUser, ...]:
    active = {item.username: item.is_active for item in seed_user_specs()}
    return tuple(
        SyntheticFixtureUser(
            username,
            synthetic_user_id(username),
            active[username],
        )
        for username in dict.fromkeys(item.username for item in synthetic_posting_specs())
    )


def test_fixture_applies_full_manifest_atomically_and_replays(
    postgres_database_url: str,
) -> None:
    _upgrade(postgres_database_url)
    engine = create_engine(postgres_database_url)
    store = PostgresSyntheticOrganisationFixtureStore(engine)
    users = _users()
    actor_id = synthetic_user_id("admin@example.test")
    preview = store.preview(actor_id, users)
    assert preview.can_apply
    assert preview.creates.units == 25
    assert preview.creates.delivery_profiles == 7
    assert preview.creates.memberships == 54
    assert preview.creates.working_patterns == 24
    assert preview.creates.grants == (
        len(ManagementAction) + len(synthetic_management_grants()) + len(synthetic_service_grants())
    )
    assert preview.creates.team_capabilities == 61
    assert preview.creates.competencies == 48
    assert preview.creates.calendar_events == 8
    assert preview.creates.tasks == 24
    assert preview.creates.task_ownership == 24
    assert preview.creates.work_packages == 48
    assert preview.creates.capacity_reservations == 2

    command_id = uuid4()
    fixture_command = SyntheticFixtureCommand(
        command_id,
        "postgres-synthetic-fixture-1",
        actor_id,
        preview.preview_hash,
    )
    result = store.apply(fixture_command, users)
    replay = store.apply(fixture_command, users)
    assert result.created.total == preview.creates.total
    assert replay.replayed

    with engine.connect() as connection:
        counts = dict(
            connection.execute(
                text(
                    "SELECT 'organisation_units',count(*) FROM organisation_units UNION ALL "
                    "SELECT 'team_delivery_profiles',count(*) FROM team_delivery_profiles "
                    "UNION ALL SELECT 'team_memberships',count(*) FROM team_memberships "
                    "UNION ALL SELECT 'working_patterns',count(*) FROM working_patterns "
                    "UNION ALL SELECT 'team_management_grants',count(*) "
                    "FROM team_management_grants UNION ALL "
                    "SELECT 'team_capability_coverage',count(*) "
                    "FROM team_capability_coverage UNION ALL "
                    "SELECT 'assignment_competencies',count(*) "
                    "FROM assignment_competencies UNION ALL "
                    "SELECT 'calendar_events',count(*) FROM calendar_events UNION ALL "
                    "SELECT 'calendar_event_scopes',count(*) FROM calendar_event_scopes "
                    "UNION ALL SELECT 'calendar_event_versions',count(*) "
                    "FROM calendar_event_versions UNION ALL "
                    "SELECT 'calendar_event_commands',count(*) FROM calendar_event_commands"
                    " UNION ALL SELECT 'coeus_ticket_aggregates',count(*) "
                    "FROM coeus_ticket_aggregates"
                    " UNION ALL SELECT 'team_task_ownership',count(*) FROM team_task_ownership"
                    " UNION ALL SELECT 'canonical_work_packages',count(*) "
                    "FROM canonical_work_packages"
                    " UNION ALL SELECT 'work_package_dependencies',count(*) "
                    "FROM work_package_dependencies"
                    " UNION ALL SELECT 'work_package_participants',count(*) "
                    "FROM work_package_participants"
                    " UNION ALL SELECT 'work_package_history',count(*) FROM work_package_history"
                    " UNION ALL SELECT 'work_package_commands',count(*) FROM work_package_commands"
                    " UNION ALL SELECT 'capacity_reservations',count(*) FROM capacity_reservations"
                )
            ).all()
        )
        analyst_lifecycle = dict(
            connection.execute(
                text(
                    "SELECT state,count(*) FROM team_memberships "
                    "WHERE user_id IN (SELECT user_id FROM working_patterns) GROUP BY state"
                )
            ).all()
        )
        eligible = connection.execute(
            text(
                "SELECT count(*) FROM team_memberships WHERE assignment_eligible AND state='active'"
            )
        ).scalar_one()
        part_time = connection.execute(
            text("SELECT monday_minutes FROM working_patterns WHERE monday_minutes=360")
        ).scalar_one()
        events = connection.execute(
            text(
                "SELECT count(*) FROM coeus_audit_events "
                "WHERE event_type='synthetic_organisation_fixture_applied'"
            )
        ).scalar_one()
    assert counts == {
        "organisation_units": 25,
        "team_delivery_profiles": 7,
        "team_memberships": 54,
        "working_patterns": 24,
        "team_management_grants": (
            len(ManagementAction)
            + len(synthetic_management_grants())
            + len(synthetic_service_grants())
        ),
        "team_capability_coverage": 61,
        "assignment_competencies": 48,
        "calendar_events": 8,
        "calendar_event_scopes": 9,
        "calendar_event_versions": 8,
        "calendar_event_commands": 8,
        "coeus_ticket_aggregates": 24,
        "team_task_ownership": 24,
        "canonical_work_packages": 48,
        "work_package_dependencies": 24,
        "work_package_participants": 26,
        "work_package_history": 48,
        "work_package_commands": 48,
        "capacity_reservations": 2,
    }
    assert analyst_lifecycle == {"active": 22, "ended": 2, "suspended": 1}
    assert eligible == 21
    assert part_time == 360
    assert events == 1

    settled = store.preview(actor_id, users)
    assert settled.can_apply
    assert settled.creates.total == 0
    assert settled.unchanged.total == preview.creates.total
    second_admin = store.preview(synthetic_user_id("admin.2@example.test"), users)
    assert second_admin.can_apply
    assert second_admin.creates.total == 0

    assert_fixture_projections(engine, users)

    task = next(item for item in synthetic_task_specs() if item.key == "mar-2")
    reservation = ReserveCapacityCommand(
        uuid4(),
        synthetic_user_id(task.manager_username),
        synthetic_user_id(task.assignee_username or ""),
        task.ticket_id,
        task.workflow_leg,
        task.package_id(1),
        datetime(2026, 8, 4, 8, tzinfo=UTC),
        datetime(2026, 8, 4, 12, tzinfo=UTC),
        60,
        "fixture-authorised-capacity",
        1,
    )
    capacity = PostgresCapacityReservationStore(postgres_database_url)
    assert capacity.reserve(reservation).reserved_minutes == 60
    with pytest.raises(CapacityAuthorityDenied):
        capacity.reserve(
            replace(
                reservation,
                reservation_id=uuid4(),
                actor_user_id=synthetic_user_id("customer.3@example.test"),
                idempotency_key="fixture-unauthorised-capacity",
            )
        )
    with pytest.raises(CapacityReservationConflict, match="idempotency key was reused"):
        capacity.reserve(
            replace(
                reservation,
                reservation_id=uuid4(),
            )
        )

    planned_task = next(item for item in synthetic_task_specs() if item.key == "mar-2")
    planned_unit_id = next(
        item.unit_id for item in synthetic_unit_specs() if item.key == planned_task.unit_key
    )
    with engine.connect() as connection:
        grant_id = connection.execute(
            text(
                "SELECT grant_id FROM team_management_grants "
                "WHERE manager_user_id=:manager_id AND root_unit_id=:unit_id "
                "AND action='task:assign' AND revoked_at IS NULL LIMIT 1"
            ),
            {
                "manager_id": synthetic_user_id(planned_task.manager_username),
                "unit_id": planned_unit_id,
            },
        ).scalar_one()
    plan_request = WorkPackagePlanRequest(
        planned_unit_id,
        planned_task.package_id(1),
        1,
        1,
        synthetic_user_id(planned_task.assignee_username or ""),
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
    planner = PostgresWorkPackagePlanningStore(engine)
    planning_preview = planner.preview(
        synthetic_user_id(planned_task.manager_username), plan_request
    )
    planning_command = PlanWorkPackageCommand(
        uuid4(),
        "fixture-plan-and-reserve",
        synthetic_user_id(planned_task.manager_username),
        plan_request,
        planning_preview.preview_hash,
    )
    planned = planner.execute(planning_command)
    assert planned.package_version == 2 and not planned.replayed
    assert planner.execute(planning_command).replayed
    with engine.connect() as connection:
        evidence = connection.execute(
            text(
                "SELECT (SELECT count(*) FROM work_package_history "
                "WHERE package_id=:package_id AND event_type='planned_and_reserved'),"
                "(SELECT count(*) FROM coeus_audit_events "
                "WHERE event_type='work_package_planned_and_reserved'),"
                "(SELECT count(*) FROM coeus_outbox "
                "WHERE event_type='work_package_planned_and_reserved')"
            ),
            {"package_id": plan_request.package_id},
        ).one()
    assert evidence == (1, 1, 1)
    engine.dispose()


def test_fixture_refuses_foreign_roots_and_changed_fixture_rows(
    postgres_database_url: str,
) -> None:
    _upgrade(postgres_database_url)
    engine = create_engine(postgres_database_url)
    store = PostgresSyntheticOrganisationFixtureStore(engine)
    users = _users()
    actor_id = synthetic_user_id("admin@example.test")
    with engine.begin() as connection:
        foreign_id = uuid4()
        connection.execute(
            text(
                "INSERT INTO organisation_units"
                "(unit_id,name,short_name,category,parent_unit_id,is_active,valid_from,"
                "time_zone,description,provenance,version) VALUES "
                "(:id,'Local Root','LOCAL','command',NULL,true,now(),"
                "'Europe/London','Local operator data.','manual',1)"
            ),
            {"id": foreign_id},
        )
        connection.execute(
            text(
                "INSERT INTO organisation_unit_closure"
                "(ancestor_unit_id,descendant_unit_id,depth) VALUES (:id,:id,0)"
            ),
            {"id": foreign_id},
        )
    conflicted = store.preview(actor_id, users)
    assert {item.code for item in conflicted.findings} == {"foreign_root"}
    with pytest.raises(SyntheticFixtureConflict, match="contains conflicts"):
        store.apply(
            SyntheticFixtureCommand(
                uuid4(), "postgres-synthetic-fixture-conflict", actor_id, conflicted.preview_hash
            ),
            users,
        )
    with engine.connect() as connection:
        assert (
            connection.execute(
                text("SELECT name FROM organisation_units WHERE unit_id=:id"), {"id": foreign_id}
            ).scalar_one()
            == "Local Root"
        )
        assert connection.execute(text("SELECT count(*) FROM team_memberships")).scalar_one() == 0
    engine.dispose()
