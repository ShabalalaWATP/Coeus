from dataclasses import replace
from datetime import UTC, datetime
from threading import Barrier, Thread
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, event, text

from coeus.domain.access import ProductStatus
from coeus.domain.draft_audience import DraftAudienceReason
from coeus.domain.enums import TicketState
from coeus.domain.store import StoreVisibilityScope
from coeus.domain.tickets import (
    AnalystAssignment,
    IntakeDetails,
    LinkedAnalystProduct,
    RoutingRoute,
    TicketRecord,
)
from coeus.persistence.codec import encode_value
from coeus.persistence.state_store import PostgresStateStore
from coeus.repositories.tickets import InMemoryTicketRepository
from store_projection_helpers import seed_product

pytestmark = pytest.mark.postgres


def test_ticket_shadow_is_idempotent_versioned_and_removes_deleted_rows(
    postgres_database_url: str,
) -> None:
    ticket = TicketRecord(
        ticket_id=uuid4(),
        reference="TCK-SHADOW-0001",
        requester_user_id=uuid4(),
        state=TicketState.DRAFT_INTAKE,
        intake=IntakeDetails(title="Synthetic shadow ticket"),
    )
    store = PostgresStateStore(postgres_database_url)
    payload = {"counter": 1, "tickets": [encode_value(ticket)]}
    store.save("tickets", payload)
    store.save("tickets", payload)

    engine = create_engine(postgres_database_url)
    with engine.connect() as connection:
        first = connection.execute(
            text(
                "SELECT version, payload FROM coeus_ticket_aggregates WHERE ticket_id = :ticket_id"
            ),
            {"ticket_id": ticket.ticket_id},
        ).one()
    assert first.version == 1
    assert first.payload == encode_value(ticket)

    changed = replace(ticket, state=TicketState.INFO_REQUIRED)
    store.save("tickets", {"counter": 1, "tickets": [encode_value(changed)]})
    with engine.connect() as connection:
        version = connection.execute(
            text("SELECT version FROM coeus_ticket_aggregates WHERE ticket_id = :ticket_id"),
            {"ticket_id": ticket.ticket_id},
        ).scalar_one()
        outbox_count = connection.execute(text("SELECT count(*) FROM coeus_outbox")).scalar_one()
    assert version == 2
    assert outbox_count == 2

    store.save("tickets", {"counter": 1, "tickets": []})
    with engine.connect() as connection:
        count = connection.execute(
            text("SELECT count(*) FROM coeus_ticket_aggregates")
        ).scalar_one()
    assert count == 0


def test_shadow_validation_fails_closed_and_legacy_rollback_can_read(
    postgres_database_url: str,
) -> None:
    ticket = TicketRecord(
        ticket_id=uuid4(),
        reference="TCK-SHADOW-0002",
        requester_user_id=uuid4(),
        state=TicketState.DRAFT_INTAKE,
        intake=IntakeDetails(title="Shadow mismatch"),
    )
    store = PostgresStateStore(postgres_database_url)
    store.save("tickets", {"counter": 2, "tickets": [encode_value(ticket)]})
    engine = create_engine(postgres_database_url)
    with engine.begin() as connection:
        connection.execute(text("UPDATE coeus_ticket_aggregates SET canonical_hash = 'mismatch'"))

    with pytest.raises(RuntimeError, match="reconciliation failed"):
        store.load("tickets")

    legacy = PostgresStateStore(postgres_database_url, "legacy")
    assert legacy.load("tickets") is not None


def test_relational_cutover_reads_and_writes_without_legacy_ticket_namespace(
    postgres_database_url: str,
) -> None:
    store = PostgresStateStore(postgres_database_url, "relational")
    repository = InMemoryTicketRepository(store)
    ticket = TicketRecord(
        ticket_id=uuid4(),
        reference=repository.next_reference(),
        requester_user_id=uuid4(),
        state=TicketState.DRAFT_INTAKE,
        intake=IntakeDetails(title="Relational cutover"),
    )
    repository.save(ticket)

    restored = InMemoryTicketRepository(PostgresStateStore(postgres_database_url, "relational"))
    engine = create_engine(postgres_database_url)
    with engine.connect() as connection:
        legacy = connection.execute(
            text("SELECT payload FROM coeus_state WHERE namespace = 'tickets'")
        ).scalar_one_or_none()

    assert restored.get(ticket.ticket_id) == ticket
    assert restored.next_reference() == "TCK-0002"
    assert legacy is None


def test_relational_cutover_refuses_a_corrupt_aggregate_at_startup(
    postgres_database_url: str,
) -> None:
    repository = InMemoryTicketRepository(PostgresStateStore(postgres_database_url, "relational"))
    ticket = TicketRecord(
        ticket_id=uuid4(),
        reference="TCK-CORRUPT-CUTOVER",
        requester_user_id=uuid4(),
        state=TicketState.DRAFT_INTAKE,
        intake=IntakeDetails(title="Synthetic corrupt cutover"),
    )
    repository.save(ticket)
    engine = create_engine(postgres_database_url)
    with engine.begin() as connection:
        connection.execute(text("UPDATE coeus_ticket_aggregates SET canonical_hash = 'corrupt'"))

    with pytest.raises(RuntimeError, match="aggregate reconciliation failed"):
        PostgresStateStore(postgres_database_url, "relational").load_ticket_state()


def test_relational_compare_and_swap_allows_one_cross_process_winner(
    postgres_database_url: str,
) -> None:
    first = InMemoryTicketRepository(PostgresStateStore(postgres_database_url, "relational"))
    original = TicketRecord(
        ticket_id=uuid4(),
        reference=first.next_reference(),
        requester_user_id=uuid4(),
        state=TicketState.DRAFT_INTAKE,
        intake=IntakeDetails(title="Cross-process CAS"),
    )
    first.save(original)
    second = InMemoryTicketRepository(PostgresStateStore(postgres_database_url, "relational"))
    barrier = Barrier(3)
    outcomes: list[bool] = []

    def update(repository: InMemoryTicketRepository, state: TicketState) -> None:
        expected = repository.get(original.ticket_id)
        assert expected is not None
        barrier.wait()
        outcomes.append(repository.save_if_current(expected, replace(expected, state=state)))

    threads = [
        Thread(target=update, args=(first, TicketState.INFO_REQUIRED)),
        Thread(target=update, args=(second, TicketState.CANCELLED)),
    ]
    for thread in threads:
        thread.start()
    barrier.wait()
    for thread in threads:
        thread.join(timeout=10)

    assert sorted(outcomes) == [False, True]
    current = InMemoryTicketRepository(PostgresStateStore(postgres_database_url, "relational")).get(
        original.ticket_id
    )
    assert current is not None
    assert current.state in {TicketState.INFO_REQUIRED, TicketState.CANCELLED}


def test_relational_mutation_statement_count_is_stable_at_ten_thousand_rows(
    postgres_database_url: str,
) -> None:
    store = PostgresStateStore(postgres_database_url, "relational")
    original = TicketRecord(
        ticket_id=uuid4(),
        reference="TCK-PERF-0001",
        requester_user_id=uuid4(),
        state=TicketState.DRAFT_INTAKE,
        intake=IntakeDetails(title="Stable mutation work"),
    )
    first = replace(original, state=TicketState.INFO_REQUIRED)
    second = replace(first, state=TicketState.CANCELLED)
    store.save_ticket_record(encode_value(original), 1)
    engine = store._engine
    statements: list[str] = []

    def record_statement(*_args: object) -> None:
        statements.append(str(_args[2]))

    event.listen(engine, "before_cursor_execute", record_statement)
    assert store.compare_and_swap_ticket_record(encode_value(original), encode_value(first), 1)
    small_count = len(statements)
    statements.clear()
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO coeus_ticket_aggregates(
                  ticket_id, requester_user_id, state, consumes_capacity,
                  version, payload, canonical_hash
                )
                SELECT md5(value::text)::uuid, md5((value + 10000)::text)::uuid,
                       'DRAFT_INTAKE', true, 1, '{}'::jsonb, md5(value::text)
                FROM generate_series(1, 9999) AS value
                ON CONFLICT DO NOTHING
                """
            )
        )
    statements.clear()
    assert store.compare_and_swap_ticket_record(encode_value(first), encode_value(second), 1)
    large_count = len(statements)
    event.remove(engine, "before_cursor_execute", record_statement)

    assert small_count == large_count
    assert large_count <= 5


def test_relational_confirmation_failure_restores_existing_and_absent_aggregates(
    postgres_database_url: str,
) -> None:
    repository = InMemoryTicketRepository(PostgresStateStore(postgres_database_url, "relational"))
    original = TicketRecord(
        ticket_id=uuid4(),
        reference=repository.next_reference(),
        requester_user_id=uuid4(),
        state=TicketState.DRAFT_INTAKE,
        intake=IntakeDetails(title="Transactional compensation"),
    )
    repository.save(original)

    with pytest.raises(RuntimeError, match="audit unavailable"):
        repository.save_with_confirmation(
            replace(original, state=TicketState.INFO_REQUIRED),
            lambda: (_ for _ in ()).throw(RuntimeError("audit unavailable")),
        )
    restored = InMemoryTicketRepository(PostgresStateStore(postgres_database_url, "relational"))
    assert restored.get(original.ticket_id) == original

    created = replace(original, ticket_id=uuid4(), reference=repository.next_reference())
    with pytest.raises(RuntimeError, match="audit unavailable"):
        repository.save_with_confirmation(
            created,
            lambda: (_ for _ in ()).throw(RuntimeError("audit unavailable")),
        )
    restored = InMemoryTicketRepository(PostgresStateStore(postgres_database_url, "relational"))
    assert restored.get(created.ticket_id) is None


def test_draft_audience_projection_tracks_and_revokes_ticket_relationships(
    postgres_database_url: str,
) -> None:
    analyst_id = uuid4()
    manager_id = uuid4()
    product_id = uuid4()
    ticket_id = uuid4()
    assignment = AnalystAssignment(
        assignment_id=uuid4(),
        ticket_id=ticket_id,
        analyst_user_id=analyst_id,
        assigned_by_user_id=manager_id,
        route=RoutingRoute.RFA,
        created_at=datetime.now(UTC),
    )
    link = LinkedAnalystProduct(
        link_id=uuid4(),
        ticket_id=ticket_id,
        product_id=product_id,
        reference="PROD-AUDIENCE",
        title="Audience product",
        summary="Synthetic audience projection",
        linked_by_user_id=analyst_id,
        created_at=datetime.now(UTC),
    )
    ticket = TicketRecord(
        ticket_id=ticket_id,
        reference="TCK-AUDIENCE",
        requester_user_id=uuid4(),
        state=TicketState.ANALYST_IN_PROGRESS,
        intake=IntakeDetails(title="Audience projection"),
        analyst_assignments=(assignment,),
        linked_products=(link,),
    )
    store = PostgresStateStore(postgres_database_url, "relational")
    repository = InMemoryTicketRepository(store)
    repository.save(ticket)
    projection = store.draft_audience_projection()

    assert projection.contains(product_id, analyst_id, DraftAudienceReason.ASSIGNED_ANALYST)
    assert projection.contains(product_id, manager_id, DraftAudienceReason.RESPONSIBLE_MANAGER)
    assert projection.reasons_for(product_id, analyst_id) == (DraftAudienceReason.ASSIGNED_ANALYST,)

    product = seed_product()
    product = replace(
        product,
        product_id=product_id,
        created_by_user_id=uuid4(),
        metadata=replace(product.metadata, status=ProductStatus.DRAFT),
    )
    store_projection = store.store_projection()
    store_projection.save_product(product)
    analyst_scope = StoreVisibilityScope(
        acg_ids=product.metadata.acg_ids,
        clearance_level=product.metadata.classification_level,
        include_drafts=False,
        draft_principal_user_id=analyst_id,
    )
    visible = store_projection.get_visible_product(product_id, analyst_scope)
    assert visible is not None
    assert visible.product_id == product.product_id
    assert visible.metadata.status == ProductStatus.DRAFT
    assert (
        store_projection.get_visible_product(
            product_id, replace(analyst_scope, draft_principal_user_id=uuid4())
        )
        is None
    )

    updated = replace(ticket, analyst_assignments=(replace(assignment, active=False),))
    assert repository.save_if_current(ticket, updated)
    assert not projection.contains(product_id, analyst_id, DraftAudienceReason.ASSIGNED_ANALYST)
    assert store_projection.get_visible_product(product_id, analyst_scope) is None
