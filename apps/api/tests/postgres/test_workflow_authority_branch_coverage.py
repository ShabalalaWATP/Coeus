"""PostgreSQL authority branches for create and QC release transactions."""

from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from sqlalchemy import create_engine, text

from coeus.core.config import Settings
from coeus.core.permissions import Permission
from coeus.domain.access import ProductStatus
from coeus.domain.enums import TicketState
from coeus.domain.store import StoreProduct, StoreProductMetadata
from coeus.domain.tickets import IntakeDetails, TicketRecord
from coeus.domain.workflow_authority import WorkflowCommitAuthority, WorkflowCommitResult
from coeus.domain.workflow_transaction import WorkflowAuditIntent
from coeus.main import create_app
from coeus.persistence.codec import decode_value
from coeus.persistence.database_url import synchronous_database_url

pytestmark = pytest.mark.postgres


def test_authorised_create_covers_denied_and_committed_authority(
    postgres_database_url: str,
) -> None:
    app = _app(postgres_database_url)
    actor = app.state.access_services.repository.get_user_by_username("user@example.test")
    assert actor is not None
    ticket = _ticket(actor.user_id, "TCK-AUTH-CREATE", TicketState.DRAFT_INTAKE)
    audit = _audit(ticket, actor.user_id, "ticket_created")

    denied = app.state.workflow_transaction.commit_authorised_ticket_create(
        ticket,
        audit,
        WorkflowCommitAuthority(
            replace(actor, is_active=False),
            None,
            frozenset({Permission.CHAT_USE}),
        ),
    )

    assert denied is WorkflowCommitResult.AUTHORITY_REVOKED
    assert _ticket_count(postgres_database_url, ticket.ticket_id) == 0
    assert _audit_count(postgres_database_url) == 0

    committed = app.state.workflow_transaction.commit_authorised_ticket_create(
        ticket,
        audit,
        WorkflowCommitAuthority(actor, None, frozenset({Permission.CHAT_USE})),
    )

    assert committed is WorkflowCommitResult.COMMITTED
    assert _stored_ticket(postgres_database_url, ticket.ticket_id) == ticket
    assert _audit_count(postgres_database_url) == 1


def test_authorised_qc_release_covers_denied_and_committed_authority(
    postgres_database_url: str,
) -> None:
    app = _app(postgres_database_url)
    actor = app.state.access_services.repository.get_user_by_username("qc.manager@example.test")
    assert actor is not None
    ticket = _ticket(actor.user_id, "TCK-AUTH-QC", TicketState.QC_REVIEW)
    app.state.ticket_services.tickets._repository.save(ticket)
    updated = replace(ticket, state=TicketState.DISSEMINATION_READY)
    product = _product(actor.user_id)
    audit = _audit(ticket, actor.user_id, "product_released")

    denied = app.state.workflow_transaction.commit_authorised_qc_release(
        ticket,
        updated,
        product,
        audit,
        None,
        WorkflowCommitAuthority(
            replace(actor, is_active=False),
            None,
            frozenset({Permission.QC_APPROVE}),
        ),
    )

    assert denied is WorkflowCommitResult.AUTHORITY_REVOKED
    assert _stored_ticket(postgres_database_url, ticket.ticket_id) == ticket
    assert _audit_count(postgres_database_url) == 0

    committed = app.state.workflow_transaction.commit_authorised_qc_release(
        ticket,
        updated,
        product,
        audit,
        None,
        WorkflowCommitAuthority(actor, None, frozenset({Permission.QC_APPROVE})),
    )

    assert committed is WorkflowCommitResult.COMMITTED
    assert _stored_ticket(postgres_database_url, ticket.ticket_id) == updated
    assert _audit_count(postgres_database_url) == 1


def _app(database_url: str) -> FastAPI:
    return create_app(
        Settings(
            environment="test",
            argon2_memory_cost=8_192,
            database_url=database_url,
            persistence_provider="postgres",
            ticket_persistence_mode="relational",
            seed_demo_content=False,
        )
    )


def _ticket(requester_id: UUID, reference: str, state: TicketState) -> TicketRecord:
    return TicketRecord(
        ticket_id=uuid4(),
        reference=reference,
        requester_user_id=requester_id,
        state=state,
        intake=IntakeDetails(title="Synthetic authority branch"),
    )


def _product(actor_id: UUID) -> StoreProduct:
    now = datetime.now(UTC)
    return StoreProduct(
        product_id=uuid4(),
        reference="PROD-AUTH-QC",
        metadata=StoreProductMetadata(
            title="Synthetic authority product",
            summary="Synthetic summary",
            description="Synthetic description",
            product_type="assessment",
            source_type="synthetic",
            owner_team="QC",
            area_or_region="Synthetic region",
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
        created_by_user_id=actor_id,
        created_at=now,
        updated_at=now,
    )


def _audit(ticket: TicketRecord, actor_id: UUID, event_type: str) -> WorkflowAuditIntent:
    return WorkflowAuditIntent(event_type, actor_id, {"ticket_id": str(ticket.ticket_id)})


def _stored_ticket(database_url: str, ticket_id: UUID) -> TicketRecord:
    with create_engine(synchronous_database_url(database_url)).connect() as connection:
        payload = connection.execute(
            text(
                "SELECT payload FROM coeus_ticket_aggregates "
                "WHERE ticket_id = CAST(:ticket_id AS uuid)"
            ),
            {"ticket_id": str(ticket_id)},
        ).scalar_one()
    value = decode_value(dict(payload))
    assert isinstance(value, TicketRecord)
    return value


def _ticket_count(database_url: str, ticket_id: UUID) -> int:
    with create_engine(synchronous_database_url(database_url)).connect() as connection:
        return int(
            connection.execute(
                text(
                    "SELECT count(*) FROM coeus_ticket_aggregates "
                    "WHERE ticket_id = CAST(:ticket_id AS uuid)"
                ),
                {"ticket_id": str(ticket_id)},
            ).scalar_one()
        )


def _audit_count(database_url: str) -> int:
    with create_engine(synchronous_database_url(database_url)).connect() as connection:
        return int(connection.execute(text("SELECT count(*) FROM coeus_audit_events")).scalar_one())
