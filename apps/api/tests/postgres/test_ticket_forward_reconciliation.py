import json
from dataclasses import replace
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text

from coeus.domain.enums import TicketState
from coeus.domain.tickets import IntakeDetails, TicketRecord
from coeus.persistence.codec import decode_value, encode_value
from coeus.persistence.state_store import PostgresStateStore
from coeus.persistence.ticket_forward_reconciliation import (
    ROLLBACK_CHECKPOINT_NAMESPACE,
    reconcile_legacy_ticket_state,
)
from coeus.persistence.ticket_reverse_projection import reverse_project_ticket_state
from coeus.repositories.tickets import InMemoryTicketRepository

pytestmark = pytest.mark.postgres


def _seed(database_url: str) -> TicketRecord:
    repository = InMemoryTicketRepository(PostgresStateStore(database_url, "relational"))
    ticket = TicketRecord(
        ticket_id=uuid4(),
        reference=repository.next_reference(),
        requester_user_id=uuid4(),
        state=TicketState.DRAFT_INTAKE,
        intake=IntakeDetails(title="N-1 compatibility"),
    )
    repository.save(ticket)
    return ticket


def _legacy_update(database_url: str, ticket: TicketRecord) -> None:
    engine = create_engine(database_url)
    with engine.begin() as connection:
        payload = dict(
            connection.execute(
                text("SELECT payload FROM coeus_state WHERE namespace='tickets'")
            ).scalar_one()
        )
        encoded = list(payload["tickets"])
        encoded[0] = encode_value(ticket)
        payload["tickets"] = encoded
        connection.execute(
            text(
                "UPDATE coeus_state SET payload=CAST(:payload AS jsonb), updated_at=now() "
                "WHERE namespace='tickets'"
            ),
            {"payload": json.dumps(payload)},
        )


def test_quiesced_n_minus_one_write_reconciles_forward_atomically(
    postgres_database_url: str,
) -> None:
    original = _seed(postgres_database_url)
    assert reverse_project_ticket_state(postgres_database_url) == 1
    legacy_update = replace(
        original,
        state=TicketState.INFO_REQUIRED,
        intake=replace(original.intake, title="N-1 updated title"),
    )
    _legacy_update(postgres_database_url, legacy_update)

    report = reconcile_legacy_ticket_state(
        postgres_database_url,
        operator="release-operator",
        reason="N-1 compatibility drill",
    )

    restored = InMemoryTicketRepository(
        PostgresStateStore(postgres_database_url, "relational")
    ).get(original.ticket_id)
    assert restored == legacy_update
    assert report.ticket_count == 1
    assert report.changed_count == 1
    assert report.removed_count == 0
    engine = create_engine(postgres_database_url)
    with engine.connect() as connection:
        assert (
            connection.execute(
                text("SELECT count(*) FROM coeus_state WHERE namespace=:namespace"),
                {"namespace": ROLLBACK_CHECKPOINT_NAMESPACE},
            ).scalar_one()
            == 0
        )
        audit = connection.execute(
            text(
                "SELECT metadata FROM coeus_audit_events "
                "WHERE event_type='legacy_ticket_state_reconciled'"
            )
        ).scalar_one()
    assert audit["changed_count"] == 1
    with pytest.raises(RuntimeError, match="checkpoint"):
        reconcile_legacy_ticket_state(
            postgres_database_url, operator="operator", reason="unsafe replay"
        )


def test_forward_reconciliation_refuses_concurrent_relational_change(
    postgres_database_url: str,
) -> None:
    original = _seed(postgres_database_url)
    assert reverse_project_ticket_state(postgres_database_url) == 1
    _legacy_update(postgres_database_url, replace(original, state=TicketState.INFO_REQUIRED))
    relational = InMemoryTicketRepository(PostgresStateStore(postgres_database_url, "relational"))
    assert relational.save_if_current(original, replace(original, state=TicketState.CANCELLED))

    with pytest.raises(RuntimeError, match="changed after rollback"):
        reconcile_legacy_ticket_state(
            postgres_database_url, operator="operator", reason="conflict proof"
        )

    current = InMemoryTicketRepository(PostgresStateStore(postgres_database_url, "relational")).get(
        original.ticket_id
    )
    assert current is not None and current.state == TicketState.CANCELLED


def test_forward_reconciliation_rejects_invalid_legacy_aggregate(
    postgres_database_url: str,
) -> None:
    _seed(postgres_database_url)
    assert reverse_project_ticket_state(postgres_database_url) == 1
    engine = create_engine(postgres_database_url)
    with engine.begin() as connection:
        payload = dict(
            connection.execute(
                text("SELECT payload FROM coeus_state WHERE namespace='tickets'")
            ).scalar_one()
        )
        payload["tickets"] = [{"not": "a ticket"}]
        connection.execute(
            text(
                "UPDATE coeus_state SET payload=CAST(:payload AS jsonb) WHERE namespace='tickets'"
            ),
            {"payload": json.dumps(payload)},
        )

    with pytest.raises(RuntimeError, match="aggregate"):
        reconcile_legacy_ticket_state(
            postgres_database_url, operator="operator", reason="corruption proof"
        )

    with engine.connect() as connection:
        encoded = connection.execute(
            text("SELECT payload FROM coeus_ticket_aggregates")
        ).scalar_one()
    assert isinstance(decode_value(dict(encoded)), TicketRecord)


def test_forward_reconciliation_applies_n_minus_one_deletion(
    postgres_database_url: str,
) -> None:
    original = _seed(postgres_database_url)
    assert reverse_project_ticket_state(postgres_database_url) == 1
    engine = create_engine(postgres_database_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE coeus_state SET payload=CAST(:payload AS jsonb) WHERE namespace='tickets'"
            ),
            {"payload": json.dumps({"counter": 1, "tickets": []})},
        )

    report = reconcile_legacy_ticket_state(
        postgres_database_url,
        operator="operator",
        reason="N-1 deletion compatibility proof",
    )

    assert report.ticket_count == 0
    assert report.changed_count == 0
    assert report.removed_count == 1
    assert (
        InMemoryTicketRepository(PostgresStateStore(postgres_database_url, "relational")).get(
            original.ticket_id
        )
        is None
    )
