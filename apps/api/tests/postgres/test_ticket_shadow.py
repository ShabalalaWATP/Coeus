from dataclasses import replace
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text

from coeus.domain.enums import TicketState
from coeus.domain.tickets import IntakeDetails, TicketRecord
from coeus.persistence.codec import encode_value
from coeus.persistence.state_store import PostgresStateStore

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
