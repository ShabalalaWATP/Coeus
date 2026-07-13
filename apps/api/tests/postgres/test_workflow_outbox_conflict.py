from dataclasses import replace
from datetime import UTC, datetime
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


def _seed(database_url: str) -> tuple[TicketRecord, StoreProduct]:
    ticket = TicketRecord(
        ticket_id=uuid4(),
        reference="TCK-OUTBOX-CONFLICT",
        requester_user_id=uuid4(),
        state=TicketState.QC_REVIEW,
        intake=IntakeDetails(title="Synthetic outbox conflict"),
    )
    now = datetime.now(UTC)
    product = StoreProduct(
        product_id=uuid4(),
        reference="PROD-OUTBOX-CONFLICT",
        metadata=StoreProductMetadata(
            title="Synthetic conflict product",
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
    InMemoryTicketRepository(PostgresStateStore(database_url, "relational")).save(ticket)
    return ticket, product


def _intents(
    ticket: TicketRecord, product: StoreProduct
) -> tuple[WorkflowAuditIntent, ReleaseNotificationIntent]:
    return (
        WorkflowAuditIntent("product_released", ticket.requester_user_id, {}),
        ReleaseNotificationIntent(
            ticket.requester_user_id,
            ticket.reference,
            product.product_id,
            product.reference,
            product.metadata.title,
        ),
    )


def test_release_fails_closed_when_the_outbox_key_has_different_content(
    postgres_database_url: str,
) -> None:
    ticket, product = _seed(postgres_database_url)
    audit, notification = _intents(ticket, product)
    engine = create_engine(postgres_database_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO coeus_outbox(event_id, aggregate_id, aggregate_version, "
                "event_type, payload) VALUES (:event_id, :ticket_id, 2, "
                "'product_release_notification', CAST('{}' AS jsonb))"
            ),
            {"event_id": uuid4(), "ticket_id": ticket.ticket_id},
        )

    with pytest.raises(RuntimeError, match="Conflicting release notification"):
        PostgresWorkflowTransaction(postgres_database_url).commit_qc_release(
            ticket,
            replace(ticket, state=TicketState.DISSEMINATION_READY),
            product,
            audit,
            notification,
        )

    restored = InMemoryTicketRepository(PostgresStateStore(postgres_database_url, "relational"))
    assert restored.get(ticket.ticket_id) == ticket
