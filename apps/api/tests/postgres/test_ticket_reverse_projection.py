from dataclasses import replace
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text

from coeus.domain.enums import TicketState
from coeus.domain.tickets import IntakeDetails, TicketRecord
from coeus.persistence.state_store import PostgresStateStore
from coeus.persistence.ticket_reverse_projection import reverse_project_ticket_state
from coeus.repositories.tickets import InMemoryTicketRepository

pytestmark = pytest.mark.postgres


def test_reverse_projection_restores_current_state_for_legacy_reader(
    postgres_database_url: str,
) -> None:
    relational = InMemoryTicketRepository(PostgresStateStore(postgres_database_url, "relational"))
    original = TicketRecord(
        ticket_id=uuid4(),
        reference=relational.next_reference(),
        requester_user_id=uuid4(),
        state=TicketState.DRAFT_INTAKE,
        intake=IntakeDetails(title="Synthetic rollback ticket"),
    )
    relational.save(original)
    updated = replace(original, state=TicketState.INFO_REQUIRED)
    assert relational.save_if_current(original, updated)

    assert reverse_project_ticket_state(postgres_database_url) == 1
    legacy = InMemoryTicketRepository(PostgresStateStore(postgres_database_url, "legacy"))

    assert legacy.get(original.ticket_id) == updated
    assert legacy.next_reference() == "TCK-0002"


def test_hash_mismatch_preserves_existing_legacy_namespace(
    postgres_database_url: str,
) -> None:
    relational = InMemoryTicketRepository(PostgresStateStore(postgres_database_url, "relational"))
    relational.save(
        TicketRecord(
            ticket_id=uuid4(),
            reference=relational.next_reference(),
            requester_user_id=uuid4(),
            state=TicketState.DRAFT_INTAKE,
            intake=IntakeDetails(title="Synthetic mismatch"),
        )
    )
    assert reverse_project_ticket_state(postgres_database_url) == 1
    engine = create_engine(postgres_database_url)
    with engine.begin() as connection:
        before = connection.execute(
            text("SELECT payload FROM coeus_state WHERE namespace = 'tickets'")
        ).scalar_one()
        connection.execute(text("UPDATE coeus_ticket_aggregates SET canonical_hash = 'tampered'"))

    with pytest.raises(RuntimeError, match="reconciliation failed"):
        reverse_project_ticket_state(postgres_database_url)
    with engine.connect() as connection:
        after = connection.execute(
            text("SELECT payload FROM coeus_state WHERE namespace = 'tickets'")
        ).scalar_one()
    assert after == before
