from dataclasses import replace
from datetime import UTC, datetime
from threading import Barrier, Thread
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text

from coeus.domain.access import ProductStatus
from coeus.domain.enums import TicketState
from coeus.domain.store import StoreProduct, StoreProductMetadata
from coeus.domain.tickets import IntakeDetails, TicketRecord
from coeus.domain.workflow_transaction import ReleaseNotificationIntent, WorkflowAuditIntent
from coeus.persistence.state_store import PostgresStateStore
from coeus.persistence.workflow_transaction import PostgresWorkflowTransaction
from coeus.repositories.tickets import InMemoryTicketRepository

pytestmark = pytest.mark.postgres

type WorkflowIntents = tuple[WorkflowAuditIntent, ReleaseNotificationIntent]


def _ticket() -> TicketRecord:
    return TicketRecord(
        ticket_id=uuid4(),
        reference="TCK-ATOMIC-0001",
        requester_user_id=uuid4(),
        state=TicketState.QC_REVIEW,
        intake=IntakeDetails(title="Synthetic atomic release"),
    )


def _product(ticket: TicketRecord) -> StoreProduct:
    now = datetime.now(UTC)
    return StoreProduct(
        product_id=uuid4(),
        reference="PROD-ATOMIC-0001",
        metadata=StoreProductMetadata(
            title="Synthetic atomic product",
            summary="Synthetic summary",
            description="Synthetic description",
            product_type="ASSESSMENT",
            source_type="SYNTHETIC",
            owner_team="Synthetic Team",
            area_or_region="Synthetic Region",
            classification_level=1,
            releasability=frozenset({"MOCK"}),
            handling_caveats=frozenset({"MOCK DATA ONLY"}),
            tags=frozenset({"synthetic"}),
            acg_ids=frozenset({uuid4()}),
            status=ProductStatus.PUBLISHED,
            time_period_start=None,
            time_period_end=None,
            geojson_ref=None,
            bounding_box=None,
        ),
        assets=(),
        created_by_user_id=ticket.requester_user_id,
        created_at=now,
        updated_at=now,
    )


def _intents(ticket: TicketRecord, product: StoreProduct) -> WorkflowIntents:
    return (
        WorkflowAuditIntent(
            "product_released",
            ticket.requester_user_id,
            {"ticket_id": str(ticket.ticket_id), "product_id": str(product.product_id)},
        ),
        ReleaseNotificationIntent(
            ticket.requester_user_id,
            ticket.reference,
            product.product_id,
            product.reference,
            product.metadata.title,
        ),
    )


def _seed(database_url: str) -> tuple[TicketRecord, StoreProduct]:
    ticket = _ticket()
    InMemoryTicketRepository(PostgresStateStore(database_url, "relational")).save(ticket)
    return ticket, _product(ticket)


def test_ticket_create_commits_new_aggregate_and_audit_and_rejects_collision(
    postgres_database_url: str,
) -> None:
    ticket = _ticket()
    audit = WorkflowAuditIntent(
        "ticket_chat_message_received",
        ticket.requester_user_id,
        {"ticket_id": str(ticket.ticket_id)},
    )
    transaction = PostgresWorkflowTransaction(postgres_database_url)

    assert transaction.commit_ticket_create(ticket, audit)
    assert not transaction.commit_ticket_create(ticket, audit)

    restored = InMemoryTicketRepository(
        PostgresStateStore(postgres_database_url, "relational")
    ).get(ticket.ticket_id)
    engine = create_engine(postgres_database_url)
    with engine.connect() as connection:
        audit_count = connection.execute(
            text("SELECT count(*) FROM coeus_audit_events")
        ).scalar_one()
    assert restored == ticket
    assert audit_count == 1


def test_ticket_create_rolls_back_aggregate_when_audit_write_fails(
    postgres_database_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    ticket = _ticket()
    audit = WorkflowAuditIntent(
        "ticket_chat_message_received",
        ticket.requester_user_id,
        {"ticket_id": str(ticket.ticket_id)},
    )

    def fail_audit(*_args: object) -> None:
        raise RuntimeError("synthetic audit failure")

    monkeypatch.setattr(PostgresWorkflowTransaction, "_append_audit", fail_audit)
    with pytest.raises(RuntimeError, match="synthetic audit failure"):
        PostgresWorkflowTransaction(postgres_database_url).commit_ticket_create(ticket, audit)

    engine = create_engine(postgres_database_url)
    with engine.connect() as connection:
        ticket_table = connection.execute(
            text("SELECT to_regclass('coeus_ticket_aggregates')")
        ).scalar_one()
        ticket_count = (
            0
            if ticket_table is None
            else connection.execute(
                text("SELECT count(*) FROM coeus_ticket_aggregates")
            ).scalar_one()
        )
    assert ticket_count == 0


def test_ticket_update_commits_state_and_audit_as_one_unit(
    postgres_database_url: str,
) -> None:
    ticket, product = _seed(postgres_database_url)
    updated = replace(ticket, state=TicketState.CANCELLED)
    audit, _notification = _intents(ticket, product)

    assert PostgresWorkflowTransaction(postgres_database_url).commit_ticket_update(
        ticket, updated, (audit,)
    )

    restored = InMemoryTicketRepository(
        PostgresStateStore(postgres_database_url, "relational")
    ).get(ticket.ticket_id)
    engine = create_engine(postgres_database_url)
    with engine.connect() as connection:
        audit_count = connection.execute(
            text("SELECT count(*) FROM coeus_audit_events")
        ).scalar_one()
    assert restored == updated
    assert audit_count == 1


def test_ticket_update_rolls_back_state_when_audit_write_fails(
    postgres_database_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    ticket, product = _seed(postgres_database_url)
    updated = replace(ticket, state=TicketState.CANCELLED)
    audit, _notification = _intents(ticket, product)

    def fail_audit(*_args: object) -> None:
        raise RuntimeError("synthetic audit failure")

    monkeypatch.setattr(PostgresWorkflowTransaction, "_append_audit", fail_audit)
    with pytest.raises(RuntimeError, match="synthetic audit failure"):
        PostgresWorkflowTransaction(postgres_database_url).commit_ticket_update(
            ticket, updated, (audit,)
        )

    restored = InMemoryTicketRepository(
        PostgresStateStore(postgres_database_url, "relational")
    ).get(ticket.ticket_id)
    assert restored == ticket


def test_qc_release_commits_ticket_product_audit_and_notification(
    postgres_database_url: str,
) -> None:
    ticket, product = _seed(postgres_database_url)
    updated = replace(ticket, state=TicketState.DISSEMINATION_READY)
    audit, notification = _intents(ticket, product)

    assert PostgresWorkflowTransaction(postgres_database_url).commit_qc_release(
        ticket, updated, product, audit, notification
    )

    restored = InMemoryTicketRepository(
        PostgresStateStore(postgres_database_url, "relational")
    ).get(ticket.ticket_id)
    engine = create_engine(postgres_database_url)
    with engine.connect() as connection:
        status = connection.execute(
            text("SELECT status FROM intelligence_store_products WHERE product_id = :id"),
            {"id": product.product_id},
        ).scalar_one()
        audit_count = connection.execute(
            text("SELECT count(*) FROM coeus_audit_events WHERE event_type = 'product_released'")
        ).scalar_one()
        notification_count = connection.execute(
            text(
                "SELECT count(*) FROM coeus_outbox "
                "WHERE event_type = 'product_release_notification'"
            )
        ).scalar_one()
    assert restored == updated
    assert status == ProductStatus.PUBLISHED.value
    assert audit_count == 1
    assert notification_count == 1


def test_qc_release_rolls_back_every_projection_when_audit_write_fails(
    postgres_database_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    ticket, product = _seed(postgres_database_url)
    updated = replace(ticket, state=TicketState.DISSEMINATION_READY)
    audit, notification = _intents(ticket, product)

    def fail_audit(*_args: object) -> None:
        raise RuntimeError("synthetic audit failure")

    monkeypatch.setattr(PostgresWorkflowTransaction, "_append_audit", fail_audit)
    with pytest.raises(RuntimeError, match="synthetic audit failure"):
        PostgresWorkflowTransaction(postgres_database_url).commit_qc_release(
            ticket, updated, product, audit, notification
        )

    restored = InMemoryTicketRepository(
        PostgresStateStore(postgres_database_url, "relational")
    ).get(ticket.ticket_id)
    engine = create_engine(postgres_database_url)
    with engine.connect() as connection:
        product_count = connection.execute(
            text("SELECT count(*) FROM intelligence_store_products WHERE product_id = :id"),
            {"id": product.product_id},
        ).scalar_one()
        audit_table = connection.execute(
            text("SELECT to_regclass('coeus_audit_events')")
        ).scalar_one()
        audit_count = (
            0
            if audit_table is None
            else connection.execute(text("SELECT count(*) FROM coeus_audit_events")).scalar_one()
        )
        notification_count = connection.execute(
            text(
                "SELECT count(*) FROM coeus_outbox "
                "WHERE event_type = 'product_release_notification'"
            )
        ).scalar_one()
    assert restored == ticket
    assert product_count == 0
    assert audit_count == 0
    assert notification_count == 0


def test_qc_release_compare_and_swap_allows_one_cross_process_winner(
    postgres_database_url: str,
) -> None:
    ticket, product = _seed(postgres_database_url)
    audit, notification = _intents(ticket, product)
    barrier = Barrier(2)
    results: list[bool] = []

    def commit(state: TicketState) -> None:
        barrier.wait()
        results.append(
            PostgresWorkflowTransaction(postgres_database_url).commit_qc_release(
                ticket, replace(ticket, state=state), product, audit, notification
            )
        )

    first = Thread(target=commit, args=(TicketState.DISSEMINATION_READY,))
    second = Thread(target=commit, args=(TicketState.ANALYST_ASSIGNMENT,))
    first.start()
    second.start()
    first.join()
    second.join()

    assert sorted(results) == [False, True]
    engine = create_engine(postgres_database_url)
    with engine.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM coeus_audit_events")).scalar_one() == 1
        assert (
            connection.execute(
                text(
                    "SELECT count(*) FROM coeus_outbox "
                    "WHERE event_type = 'product_release_notification'"
                )
            ).scalar_one()
            == 1
        )
