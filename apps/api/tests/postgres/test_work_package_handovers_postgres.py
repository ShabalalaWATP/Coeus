"""Real PostgreSQL evidence for accountable-owner handover."""

from dataclasses import replace
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError

from coeus.domain.work_package_handovers import (
    HandoverWorkPackageCommand,
    WorkPackageHandoverConflict,
    WorkPackageHandoverDenied,
)
from coeus.persistence.work_package_handovers_postgres import (
    PostgresWorkPackageHandoverStore,
)
from postgres.work_package_handover_support import (
    insert_handover_evidence,
    upgrade_handover_schema,
)

pytestmark = pytest.mark.postgres


def test_handover_is_atomic_replayable_and_immutable(postgres_database_url: str) -> None:
    upgrade_handover_schema(postgres_database_url)
    evidence = insert_handover_evidence(postgres_database_url)
    engine = create_engine(postgres_database_url)
    store = PostgresWorkPackageHandoverStore(engine)
    preview = store.preview(evidence.actor_id, evidence.request)
    command_id = uuid4()
    handover = HandoverWorkPackageCommand(
        command_id, "handover-command", evidence.actor_id, evidence.request, preview.preview_hash
    )

    result = store.execute(handover)
    replay = store.execute(handover)

    assert (preview.participant_count, preview.reservation_count, preview.dependency_count) == (
        3,
        2,
        1,
    )
    assert result.package_version == 2 and result.replacement_reservation_count == 1
    assert replay.replayed and replay.package_version == 2
    with engine.connect() as connection:
        package = connection.execute(
            text(
                "SELECT accountable_user_id,version FROM canonical_work_packages "
                "WHERE package_id=:id"
            ),
            {"id": evidence.package_id},
        ).one()
        participants = tuple(
            connection.execute(
                text(
                    "SELECT user_id,role,active FROM work_package_participants "
                    "WHERE package_id=:id ORDER BY role,user_id"
                ),
                {"id": evidence.package_id},
            )
        )
        reservations = tuple(
            connection.execute(
                text(
                    "SELECT user_id,state FROM capacity_reservations "
                    "WHERE package_id=:id ORDER BY created_at,reservation_id"
                ),
                {"id": evidence.package_id},
            )
        )
        counts = connection.execute(
            text(
                "SELECT (SELECT count(*) FROM work_package_history WHERE package_id=:id),"
                "(SELECT count(*) FROM coeus_audit_events "
                " WHERE event_type='work_package_handed_over'),"
                "(SELECT count(*) FROM coeus_outbox "
                " WHERE event_type='work_package_handed_over')"
            ),
            {"id": evidence.package_id},
        ).one()
    assert tuple(package) == (evidence.target_id, 2)
    assert (evidence.owner_id, "accountable", False) in participants
    assert (evidence.target_id, "accountable", True) in participants
    assert (evidence.target_id, "contributor", False) in participants
    assert (evidence.owner_id, "released") in reservations
    assert (evidence.contributor_id, "active") in reservations
    assert (evidence.target_id, "active") in reservations
    assert tuple(counts) == (1, 1, 1)
    with pytest.raises(DBAPIError), engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE work_package_handover_commands SET result_package_version=99 "
                "WHERE command_id=:id"
            ),
            {"id": command_id},
        )
    engine.dispose()


def test_dependency_change_after_preview_rolls_back(postgres_database_url: str) -> None:
    upgrade_handover_schema(postgres_database_url)
    evidence = insert_handover_evidence(postgres_database_url)
    engine = create_engine(postgres_database_url)
    store = PostgresWorkPackageHandoverStore(engine)
    preview = store.preview(evidence.actor_id, evidence.request)
    extra = uuid4()
    with engine.begin() as connection:
        row = connection.execute(
            text(
                "SELECT ticket_id,owning_unit_id,created_at FROM canonical_work_packages "
                "WHERE package_id=:id"
            ),
            {"id": evidence.package_id},
        ).one()
        connection.execute(
            text(
                "INSERT INTO canonical_work_packages"
                "(package_id,ticket_id,workflow_leg,owning_unit_id,accountable_user_id,title,state,"
                "sort_order,version,provenance,created_at,updated_at) VALUES "
                "(:id,:ticket,'rfa',:unit,:owner,'Late dependency','complete',2,1,'test',:at,:at)"
            ),
            {
                "id": extra,
                "ticket": row.ticket_id,
                "unit": row.owning_unit_id,
                "owner": evidence.owner_id,
                "at": row.created_at,
            },
        )
        connection.execute(
            text(
                "INSERT INTO work_package_dependencies"
                "(package_id,predecessor_package_id,created_by_user_id,created_at) "
                "VALUES (:package,:predecessor,:actor,:at)"
            ),
            {
                "package": evidence.package_id,
                "predecessor": extra,
                "actor": evidence.actor_id,
                "at": row.created_at,
            },
        )
    with pytest.raises(WorkPackageHandoverConflict, match="preview"):
        store.execute(
            HandoverWorkPackageCommand(
                uuid4(), "stale-handover", evidence.actor_id, evidence.request, preview.preview_hash
            )
        )
    with engine.connect() as connection:
        owner = connection.execute(
            text("SELECT accountable_user_id FROM canonical_work_packages WHERE package_id=:id"),
            {"id": evidence.package_id},
        ).scalar_one()
        state = connection.execute(
            text("SELECT state FROM capacity_reservations WHERE reservation_id=:id"),
            {"id": evidence.reservation_id},
        ).scalar_one()
    assert owner == evidence.owner_id and state == "active"
    engine.dispose()


def test_failed_capacity_and_revoked_grant_leave_source_intact(
    postgres_database_url: str,
) -> None:
    upgrade_handover_schema(postgres_database_url)
    evidence = insert_handover_evidence(postgres_database_url, target_minutes=0)
    engine = create_engine(postgres_database_url)
    store = PostgresWorkPackageHandoverStore(engine)
    preview = store.preview(evidence.actor_id, evidence.request)
    with pytest.raises(WorkPackageHandoverConflict, match="target reservation"):
        store.execute(
            HandoverWorkPackageCommand(
                uuid4(), "no-capacity", evidence.actor_id, evidence.request, preview.preview_hash
            )
        )
    with engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE team_management_grants SET revoked_at=transaction_timestamp() "
                "WHERE grant_id=:id"
            ),
            {"id": evidence.request.authorising_grant_id},
        )
    with pytest.raises(WorkPackageHandoverDenied):
        store.execute(
            HandoverWorkPackageCommand(
                uuid4(), "revoked", evidence.actor_id, evidence.request, preview.preview_hash
            )
        )
    with engine.connect() as connection:
        current = connection.execute(
            text(
                "SELECT package.accountable_user_id,reservation.state "
                "FROM canonical_work_packages package JOIN capacity_reservations reservation "
                "ON reservation.package_id=package.package_id "
                "WHERE package.package_id=:id AND reservation.reservation_id=:reservation_id"
            ),
            {"id": evidence.package_id, "reservation_id": evidence.reservation_id},
        ).one()
    assert tuple(current) == (evidence.owner_id, "active")
    engine.dispose()


def test_contributor_reservation_drift_invalidates_preview_without_releasing_it(
    postgres_database_url: str,
) -> None:
    upgrade_handover_schema(postgres_database_url)
    evidence = insert_handover_evidence(postgres_database_url)
    engine = create_engine(postgres_database_url)
    store = PostgresWorkPackageHandoverStore(engine)
    preview = store.preview(evidence.actor_id, evidence.request)
    with engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE capacity_reservations SET version=version+1 "
                "WHERE reservation_id=:reservation"
            ),
            {"reservation": evidence.contributor_reservation_id},
        )
    with pytest.raises(WorkPackageHandoverConflict, match="preview"):
        store.execute(
            HandoverWorkPackageCommand(
                uuid4(),
                "contributor-drift",
                evidence.actor_id,
                evidence.request,
                preview.preview_hash,
            )
        )
    with engine.connect() as connection:
        rows = tuple(
            connection.execute(
                text(
                    "SELECT reservation_id,state FROM capacity_reservations "
                    "WHERE package_id=:package ORDER BY reservation_id"
                ),
                {"package": evidence.package_id},
            )
        )
    assert (evidence.reservation_id, "active") in rows
    assert (evidence.contributor_reservation_id, "active") in rows
    engine.dispose()


def test_unrelated_actor_gets_generic_denial_before_version_conflict(
    postgres_database_url: str,
) -> None:
    upgrade_handover_schema(postgres_database_url)
    evidence = insert_handover_evidence(postgres_database_url)
    engine = create_engine(postgres_database_url)
    store = PostgresWorkPackageHandoverStore(engine)
    stale = replace(evidence.request, expected_package_version=999)
    with pytest.raises(WorkPackageHandoverDenied):
        store.preview(uuid4(), stale)
    engine.dispose()


def test_replay_denies_old_unit_manager_after_ownership_transfer(
    postgres_database_url: str,
) -> None:
    upgrade_handover_schema(postgres_database_url)
    evidence = insert_handover_evidence(postgres_database_url)
    engine = create_engine(postgres_database_url)
    store = PostgresWorkPackageHandoverStore(engine)
    preview = store.preview(evidence.actor_id, evidence.request)
    command = HandoverWorkPackageCommand(
        uuid4(), "ownership-replay", evidence.actor_id, evidence.request, preview.preview_hash
    )
    store.execute(command)
    new_unit = uuid4()
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO organisation_units"
                "(unit_id,name,short_name,category,is_active,valid_from,time_zone,provenance,"
                "version) VALUES (:unit,'New owning unit','NEW','delivery_team',true,"
                "transaction_timestamp(),'Europe/London','test',1)"
            ),
            {"unit": new_unit},
        )
        connection.execute(
            text(
                "INSERT INTO organisation_unit_closure"
                "(ancestor_unit_id,descendant_unit_id,depth) VALUES (:unit,:unit,0)"
            ),
            {"unit": new_unit},
        )
        connection.execute(
            text(
                "UPDATE team_task_ownership SET owning_unit_id=:unit "
                "WHERE ticket_id=(SELECT ticket_id FROM canonical_work_packages "
                "WHERE package_id=:package) AND workflow_leg='rfa'"
            ),
            {"unit": new_unit, "package": evidence.package_id},
        )
        connection.execute(
            text(
                "UPDATE canonical_work_packages SET owning_unit_id=:unit WHERE package_id=:package"
            ),
            {"unit": new_unit, "package": evidence.package_id},
        )
    with pytest.raises(WorkPackageHandoverDenied):
        store.execute(command)
    engine.dispose()
