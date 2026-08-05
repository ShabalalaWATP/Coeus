"""Real PostgreSQL concurrency evidence for lifecycle conservation."""

from dataclasses import replace
from threading import Barrier, Thread
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text

from coeus.domain.team_task_ownership import WorkflowLeg
from coeus.domain.work_package_dependencies import (
    ChangeDependencyCommand,
    DependencyChangeRequest,
    DependencyOperation,
    WorkPackageDependencyConflict,
)
from coeus.domain.work_packages import CapacityUnavailable, ReserveCapacityCommand
from coeus.persistence.capacity_reservations_postgres import PostgresCapacityReservationStore
from coeus.persistence.work_package_dependencies_postgres import (
    PostgresWorkPackageDependencyStore,
)
from postgres.package_lifecycle_support import lifecycle_fixture

pytestmark = pytest.mark.postgres


def test_competing_capacity_reservations_have_one_safe_winner(
    postgres_database_url: str,
) -> None:
    evidence = lifecycle_fixture(postgres_database_url)
    engine = create_engine(postgres_database_url)
    with engine.begin() as connection:
        starts_at, ends_at = connection.execute(
            text("SELECT starts_at,ends_at FROM capacity_reservations LIMIT 1")
        ).one()
        connection.execute(
            text(
                "UPDATE canonical_work_packages SET estimated_minutes=480,remaining_minutes=480 "
                "WHERE package_id=:id"
            ),
            {"id": evidence.package_id},
        )
    commands = [
        ReserveCapacityCommand(
            uuid4(),
            evidence.actor_id,
            evidence.target_id,
            evidence.ticket.ticket_id,
            WorkflowLeg.RFA,
            evidence.package_id,
            starts_at,
            ends_at,
            180,
            f"reservation-race-{index}",
            1,
            "contributor",
        )
        for index in range(2)
    ]
    barrier, outcomes = Barrier(2), []

    def reserve(item: ReserveCapacityCommand) -> None:
        barrier.wait()
        try:
            PostgresCapacityReservationStore(postgres_database_url).reserve(item)
        except CapacityUnavailable:
            outcomes.append("rejected")
        else:
            outcomes.append("reserved")

    threads = [Thread(target=reserve, args=(item,)) for item in commands]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sorted(outcomes) == ["rejected", "reserved"]
    engine.dispose()


def test_concurrent_opposite_dependency_edges_have_one_safe_winner(
    postgres_database_url: str,
) -> None:
    evidence = lifecycle_fixture(postgres_database_url)
    engine = create_engine(postgres_database_url)
    with engine.begin() as connection:
        connection.execute(
            text("DELETE FROM work_package_dependencies WHERE package_id=:package"),
            {"package": evidence.package_id},
        )
        connection.execute(
            text(
                "UPDATE canonical_work_packages SET state='ready',remaining_minutes=120 "
                "WHERE package_id=:id"
            ),
            {"id": evidence.predecessor_id},
        )
    request = DependencyChangeRequest(
        evidence.unit_id,
        evidence.package_id,
        evidence.predecessor_id,
        DependencyOperation.ADD,
        1,
        1,
        2,
        evidence.request.authorising_grant_id,
        evidence.request.expected_grant_version,
    )
    inverse = replace(
        request,
        package_id=evidence.predecessor_id,
        predecessor_package_id=evidence.package_id,
    )
    store = PostgresWorkPackageDependencyStore(engine)
    previews = (
        store.preview(evidence.actor_id, request),
        store.preview(evidence.actor_id, inverse),
    )
    commands = (
        ChangeDependencyCommand(
            uuid4(), "edge-forward", evidence.actor_id, request, previews[0].preview_hash
        ),
        ChangeDependencyCommand(
            uuid4(), "edge-reverse", evidence.actor_id, inverse, previews[1].preview_hash
        ),
    )
    barrier, outcomes = Barrier(2), []

    def add_edge(item: ChangeDependencyCommand) -> None:
        barrier.wait()
        try:
            PostgresWorkPackageDependencyStore(create_engine(postgres_database_url)).execute(item)
        except WorkPackageDependencyConflict:
            outcomes.append("rejected")
        else:
            outcomes.append("added")

    threads = [Thread(target=add_edge, args=(item,)) for item in commands]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sorted(outcomes) == ["added", "rejected"]
    engine.dispose()
