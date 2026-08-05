"""Capacity reservation bounds for a projected work package."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from organisation_account_support import activate_analysts, activate_principals
from sqlalchemy import create_engine, text
from test_assignment_ownership_transaction import _ticket, _upgrade

from coeus.domain.enums import TicketState
from coeus.domain.organisation_bootstrap import OrganisationBootstrapPlan
from coeus.domain.team_task_ownership import AssignmentOwnershipIntent, WorkflowLeg
from coeus.domain.tickets import (
    AnalystAssignment,
    AnalystWorkPackage,
    RoutingRoute,
    WorkPackageStatus,
)
from coeus.domain.work_packages import (
    CapacityReservationConflict,
    CapacityUnavailable,
    CapacityUnknown,
    ReserveCapacityCommand,
)
from coeus.domain.workflow_transaction import WorkflowAuditIntent
from coeus.persistence.capacity_reservations_postgres import PostgresCapacityReservationStore
from coeus.persistence.organisation_bootstrap_postgres import PostgresOrganisationBootstrapStore
from coeus.persistence.state_store import PostgresStateStore
from coeus.persistence.workflow_transaction import PostgresWorkflowTransaction
from coeus.repositories.tickets import InMemoryTicketRepository

pytestmark = pytest.mark.postgres


def test_assignment_projects_packages_with_one_current_home_team_owner(
    postgres_database_url: str,
) -> None:
    _upgrade(postgres_database_url)
    engine = create_engine(postgres_database_url)
    actor_id, analyst_id, unit_id = uuid4(), uuid4(), uuid4()
    PostgresOrganisationBootstrapStore(engine).bootstrap(
        OrganisationBootstrapPlan(
            uuid4(), actor_id, unit_id, "Synthetic Team", "SYN", "Europe/London", ""
        )
    )
    activate_principals(engine, actor_id)
    activate_analysts(engine, analyst_id)
    now = datetime.now(UTC)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO team_delivery_profiles"
                "(profile_id,unit_id,route,wip_limit,weekly_hours,policy_version,"
                "is_active,provenance) VALUES "
                "(:profile,:unit,'rfa',8,40,3,true,'synthetic-test')"
            ),
            {"profile": uuid4(), "unit": unit_id},
        )
        connection.execute(
            text(
                "INSERT INTO team_memberships"
                "(membership_id,user_id,unit_id,role,state,assignment_eligible,valid_from,"
                "created_by_user_id,reason,provenance,version) VALUES "
                "(:membership,:user,:unit,'member','active',true,:now,:actor,"
                "'Synthetic assignment','synthetic-test',1)"
            ),
            {
                "membership": uuid4(),
                "user": analyst_id,
                "unit": unit_id,
                "now": now,
                "actor": actor_id,
            },
        )
    ticket = _ticket()
    repository = InMemoryTicketRepository(PostgresStateStore(postgres_database_url, "relational"))
    repository.save(ticket)
    assignment = AnalystAssignment(
        uuid4(), ticket.ticket_id, analyst_id, actor_id, RoutingRoute.RFA, now, unit_id
    )
    package = AnalystWorkPackage(
        uuid4(),
        ticket.ticket_id,
        "Assess synthetic reporting",
        WorkPackageStatus.PENDING,
        1,
        now,
    )
    updated = replace(
        ticket,
        state=TicketState.ANALYST_IN_PROGRESS,
        analyst_assignments=(assignment,),
        work_packages=(package,),
    )
    assert PostgresWorkflowTransaction(postgres_database_url).commit_ticket_assignment(
        ticket,
        updated,
        (WorkflowAuditIntent("analyst_assigned", actor_id, {"ticket_id": str(ticket.ticket_id)}),),
        AssignmentOwnershipIntent(unit_id, WorkflowLeg.RFA, actor_id, uuid4()),
    )
    reservation_start = datetime(2026, 8, 4, 8, tzinfo=UTC)
    with engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE canonical_work_packages SET state='ready',estimated_minutes=120,"
                "remaining_minutes=120 WHERE package_id=:package_id"
            ),
            {"package_id": package.package_id},
        )
        connection.execute(
            text(
                "INSERT INTO working_patterns(pattern_id,user_id,time_zone,monday_minutes,"
                "tuesday_minutes,wednesday_minutes,thursday_minutes,friday_minutes,"
                "saturday_minutes,sunday_minutes,valid_from,version,provenance,created_at,updated_at)"
                " VALUES (:pattern,:user,'Europe/London',480,480,480,480,480,0,0,:valid,1,"
                "'synthetic-test',:valid,:valid)"
            ),
            {
                "pattern": uuid4(),
                "user": analyst_id,
                "valid": reservation_start - timedelta(days=1),
            },
        )
        # Capacity is only reserved inside a current home posting, so the
        # posting has to start before the reserved window rather than at "now".
        connection.execute(
            text("UPDATE team_memberships SET valid_from=:valid WHERE user_id=:user"),
            {"valid": reservation_start - timedelta(days=1), "user": analyst_id},
        )
    reserve = ReserveCapacityCommand(
        uuid4(),
        actor_id,
        analyst_id,
        ticket.ticket_id,
        WorkflowLeg.RFA,
        package.package_id,
        reservation_start,
        reservation_start + timedelta(hours=4),
        60,
        "synthetic-capacity-1",
        1,
    )
    reservation_store = PostgresCapacityReservationStore(postgres_database_url)
    with pytest.raises(ValueError, match="policy buffer"):
        PostgresCapacityReservationStore(postgres_database_url, policy_buffer_minutes=1)
    for changes, message in (
        ({"package_id": uuid4(), "idempotency_key": "missing-package"}, "unavailable"),
        ({"expected_package_version": 2, "idempotency_key": "stale-package"}, "version"),
        ({"ticket_id": uuid4(), "idempotency_key": "wrong-ticket"}, "authority"),
        # Reservations cover contributors too, so the refusal names the participant.
        ({"user_id": uuid4(), "idempotency_key": "wrong-owner"}, "active package participant"),
    ):
        with pytest.raises(CapacityReservationConflict, match=message):
            reservation_store.reserve(replace(reserve, reservation_id=uuid4(), **changes))
    with pytest.raises(CapacityUnavailable, match="assignable capacity"):
        reservation_store.reserve(
            replace(
                reserve,
                reservation_id=uuid4(),
                reserved_minutes=300,
                idempotency_key="over-capacity",
            )
        )
    with engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE canonical_work_packages SET estimated_minutes=NULL,remaining_minutes=NULL "
                "WHERE package_id=:package_id"
            ),
            {"package_id": package.package_id},
        )
    with pytest.raises(CapacityUnknown, match="refined effort"):
        reservation_store.reserve(
            replace(reserve, reservation_id=uuid4(), idempotency_key="missing-estimate")
        )
    with engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE canonical_work_packages SET estimated_minutes=120,remaining_minutes=120 "
                "WHERE package_id=:package_id"
            ),
            {"package_id": package.package_id},
        )
    assert reservation_store.reserve(reserve).reserved_minutes == 60
    assert reservation_store.reserve(reserve).reservation_id == reserve.reservation_id
    with pytest.raises(CapacityReservationConflict, match="reused"):
        reservation_store.reserve(replace(reserve, reservation_id=uuid4()))
    with pytest.raises(CapacityReservationConflict, match="reused"):
        reservation_store.reserve(replace(reserve, reserved_minutes=75))
    # A re-plan is measured against the package's remaining effort alone:
    # existing reservations are commitments, not completed work.
    with engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE canonical_work_packages SET remaining_minutes=30 "
                "WHERE package_id=:package_id"
            ),
            {"package_id": package.package_id},
        )
    with pytest.raises(CapacityUnavailable, match="remaining effort"):
        reservation_store.reserve(
            replace(
                reserve,
                reservation_id=uuid4(),
                reserved_minutes=60,
                idempotency_key="synthetic-capacity-2",
            )
        )
    completed = replace(
        updated,
        work_packages=(replace(package, status=WorkPackageStatus.COMPLETE),),
    )
    assert PostgresWorkflowTransaction(postgres_database_url).commit_ticket_update(
        updated,
        completed,
        (
            WorkflowAuditIntent(
                "work_package_updated", actor_id, {"ticket_id": str(ticket.ticket_id)}
            ),
        ),
    )
    with engine.connect() as connection:
        projected = (
            connection.execute(text("SELECT * FROM canonical_work_packages")).mappings().one()
        )
        participant = (
            connection.execute(text("SELECT * FROM work_package_participants")).mappings().one()
        )
        history = tuple(
            connection.execute(
                text("SELECT * FROM work_package_history ORDER BY version")
            ).mappings()
        )
        reservation_state = connection.execute(
            text("SELECT state FROM capacity_reservations")
        ).scalar_one()
    assert projected["package_id"] == package.package_id
    assert projected["accountable_user_id"] == analyst_id
    assert projected["owning_unit_id"] == unit_id and projected["state"] == "complete"
    # Completing the package closes out its participants and their capacity.
    assert participant["user_id"] == analyst_id and not participant["active"]
    assert [row["event_type"] for row in history] == ["assignment_projection", "status_changed"]
    assert reservation_state == "released"
    engine.dispose()
