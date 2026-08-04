"""PostgreSQL concurrency and actor-scoped idempotency evidence."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from threading import Barrier
from time import monotonic, sleep
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text

from coeus.domain.work_package_handovers import (
    HandoverWorkPackageCommand,
    WorkPackageHandoverConflict,
)
from coeus.persistence.work_package_handovers_postgres import (
    PostgresWorkPackageHandoverStore,
)
from postgres.work_package_handover_concurrency_support import (
    add_authorised_actor,
    clone_handover_package,
)
from postgres.work_package_handover_support import (
    insert_handover_evidence,
    upgrade_handover_schema,
)

pytestmark = pytest.mark.postgres


def test_same_actor_key_serialises_different_package_commands(
    postgres_database_url: str,
) -> None:
    upgrade_handover_schema(postgres_database_url)
    evidence = insert_handover_evidence(postgres_database_url)
    engine = create_engine(postgres_database_url)
    store = PostgresWorkPackageHandoverStore(engine)
    second_request = clone_handover_package(engine, evidence)
    requests = (evidence.request, second_request)
    previews = tuple(store.preview(evidence.actor_id, request) for request in requests)
    barrier = Barrier(2)

    def execute(index: int) -> str:
        barrier.wait()
        try:
            store.execute(
                HandoverWorkPackageCommand(
                    uuid4(),
                    "shared-handover-key",
                    evidence.actor_id,
                    requests[index],
                    previews[index].preview_hash,
                )
            )
        except WorkPackageHandoverConflict:
            return "conflict"
        return "committed"

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = tuple(executor.map(execute, (0, 1)))
    assert sorted(outcomes) == ["committed", "conflict"]
    with engine.connect() as connection:
        owners = tuple(
            connection.execute(
                text(
                    "SELECT accountable_user_id FROM canonical_work_packages "
                    "WHERE package_id=ANY(CAST(:packages AS uuid[])) ORDER BY package_id"
                ),
                {"packages": [request.package_id for request in requests]},
            ).scalars()
        )
        commands = connection.execute(
            text(
                "SELECT count(*) FROM work_package_handover_commands "
                "WHERE actor_user_id=:actor AND idempotency_key='shared-handover-key'"
            ),
            {"actor": evidence.actor_id},
        ).scalar_one()
    assert owners.count(evidence.target_id) == 1
    assert owners.count(evidence.owner_id) == 1
    assert commands == 1
    engine.dispose()


def test_same_key_is_independent_for_two_authorised_actors(
    postgres_database_url: str,
) -> None:
    upgrade_handover_schema(postgres_database_url)
    evidence = insert_handover_evidence(postgres_database_url)
    engine = create_engine(postgres_database_url)
    store = PostgresWorkPackageHandoverStore(engine)
    actor_two, grant_two = add_authorised_actor(engine, evidence)
    second_request = replace(
        clone_handover_package(engine, evidence),
        authorising_grant_id=grant_two,
        expected_grant_version=1,
    )
    second_request = replace(
        second_request,
        reservations=(
            replace(
                second_request.reservations[0],
                replacement_idempotency_key=(
                    evidence.request.reservations[0].replacement_idempotency_key
                ),
            ),
        ),
    )
    preview_one = store.preview(evidence.actor_id, evidence.request)

    first = store.execute(
        HandoverWorkPackageCommand(
            uuid4(),
            "actor-scoped-key",
            evidence.actor_id,
            evidence.request,
            preview_one.preview_hash,
        )
    )
    preview_two = store.preview(actor_two, second_request)
    second = store.execute(
        HandoverWorkPackageCommand(
            uuid4(), "actor-scoped-key", actor_two, second_request, preview_two.preview_hash
        )
    )

    assert first.package_version == second.package_version == 2
    with engine.connect() as connection:
        actors = set(
            connection.execute(
                text(
                    "SELECT actor_user_id FROM work_package_handover_commands "
                    "WHERE idempotency_key='actor-scoped-key'"
                )
            ).scalars()
        )
        reservation_actors = set(
            connection.execute(
                text(
                    "SELECT actor_user_id FROM capacity_reservations "
                    "WHERE idempotency_key='target-replacement'"
                )
            ).scalars()
        )
    assert actors == {evidence.actor_id, actor_two}
    assert reservation_actors == {evidence.actor_id, actor_two}
    engine.dispose()


def test_same_actor_capacity_key_rejects_different_replacement(
    postgres_database_url: str,
) -> None:
    upgrade_handover_schema(postgres_database_url)
    evidence = insert_handover_evidence(postgres_database_url)
    engine = create_engine(postgres_database_url)
    store = PostgresWorkPackageHandoverStore(engine)
    second = clone_handover_package(engine, evidence)
    second = replace(
        second,
        reservations=(
            replace(
                second.reservations[0],
                replacement_idempotency_key="target-replacement",
            ),
        ),
    )
    first_preview = store.preview(evidence.actor_id, evidence.request)
    store.execute(
        HandoverWorkPackageCommand(
            uuid4(),
            "first-package",
            evidence.actor_id,
            evidence.request,
            first_preview.preview_hash,
        )
    )
    second_preview = store.preview(evidence.actor_id, second)
    with pytest.raises(WorkPackageHandoverConflict, match="could not be created"):
        store.execute(
            HandoverWorkPackageCommand(
                uuid4(), "second-package", evidence.actor_id, second, second_preview.preview_hash
            )
        )
    engine.dispose()


def test_handover_locks_ticket_before_package(postgres_database_url: str) -> None:
    upgrade_handover_schema(postgres_database_url)
    evidence = insert_handover_evidence(postgres_database_url)
    engine = create_engine(postgres_database_url)
    worker_engine = create_engine(
        postgres_database_url,
        connect_args={"application_name": "handover-lock-order"},
    )
    store = PostgresWorkPackageHandoverStore(worker_engine)
    preview = store.preview(evidence.actor_id, evidence.request)
    command = HandoverWorkPackageCommand(
        uuid4(), "lock-order", evidence.actor_id, evidence.request, preview.preview_hash
    )

    executor = ThreadPoolExecutor(max_workers=1)
    with engine.connect() as blocker:
        transaction = blocker.begin()
        blocker.execute(
            text("SELECT 1 FROM coeus_ticket_aggregates WHERE ticket_id=:ticket FOR UPDATE"),
            {"ticket": evidence.ticket.ticket_id},
        ).one()
        future = executor.submit(store.execute, command)
        try:
            deadline = monotonic() + 5
            waiting = False
            while monotonic() < deadline:
                waiting = bool(
                    blocker.execute(
                        text(
                            "SELECT EXISTS(SELECT 1 FROM pg_stat_activity "
                            "WHERE application_name='handover-lock-order' "
                            "AND wait_event_type='Lock')"
                        )
                    ).scalar_one()
                )
                if waiting:
                    break
                sleep(0.01)
            assert waiting
            blocker.execute(
                text(
                    "SELECT 1 FROM canonical_work_packages "
                    "WHERE package_id=:package FOR UPDATE NOWAIT"
                ),
                {"package": evidence.package_id},
            ).one()
        finally:
            transaction.rollback()
        assert future.result(timeout=10).package_version == 2
    executor.shutdown()
    worker_engine.dispose()
    engine.dispose()
