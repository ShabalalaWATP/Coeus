from dataclasses import replace
from datetime import UTC, datetime
from threading import Barrier, Thread
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, text

from coeus.domain.enums import TicketState
from coeus.domain.tickets import IntakeDetails, LinkedAnalystProduct, TicketRecord
from coeus.domain.workflow_transaction import WorkflowAuditIntent
from coeus.persistence.state_store import PostgresStateStore
from coeus.persistence.workflow_transaction import PostgresWorkflowTransaction
from coeus.repositories.tickets import InMemoryTicketRepository

pytestmark = pytest.mark.postgres


def _seed(database_url: str) -> tuple[TicketRecord, UUID]:
    product_id = uuid4()
    ticket = TicketRecord(
        ticket_id=uuid4(),
        reference="TCK-QC-CLAIM",
        requester_user_id=uuid4(),
        state=TicketState.QC_REVIEW,
        intake=IntakeDetails(title="Synthetic concurrent QC claim"),
        linked_products=(
            LinkedAnalystProduct(
                link_id=uuid4(),
                ticket_id=uuid4(),
                product_id=product_id,
                reference="PROD-QC-CLAIM",
                title="Synthetic linked draft",
                summary="Synthetic claim audience",
                linked_by_user_id=uuid4(),
                created_at=datetime.now(UTC),
            ),
        ),
    )
    link = replace(ticket.linked_products[0], ticket_id=ticket.ticket_id)
    ticket = replace(ticket, linked_products=(link,))
    InMemoryTicketRepository(PostgresStateStore(database_url, "relational")).save(ticket)
    return ticket, product_id


def test_postgres_claim_race_commits_one_reviewer_audit_and_audience(
    postgres_database_url: str,
) -> None:
    ticket, product_id = _seed(postgres_database_url)
    reviewers = (uuid4(), uuid4())
    barrier = Barrier(2)
    results: list[tuple[UUID, bool]] = []

    def claim(reviewer_id: UUID) -> None:
        barrier.wait(timeout=5)
        proposed = replace(
            ticket,
            qc_reviewer_user_id=reviewer_id,
            qc_claimed_at=datetime.now(UTC),
        )
        committed = PostgresWorkflowTransaction(postgres_database_url).commit_ticket_update(
            ticket,
            proposed,
            (WorkflowAuditIntent("qc_claimed", reviewer_id, {"ticket_id": str(ticket.ticket_id)}),),
        )
        results.append((reviewer_id, committed))

    threads = [Thread(target=claim, args=(reviewer,)) for reviewer in reviewers]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    assert all(not thread.is_alive() for thread in threads)
    assert sum(int(committed) for _reviewer, committed in results) == 1
    winner = next(reviewer for reviewer, committed in results if committed)
    restored = InMemoryTicketRepository(
        PostgresStateStore(postgres_database_url, "relational")
    ).get(ticket.ticket_id)
    assert restored is not None and restored.qc_reviewer_user_id == winner
    with create_engine(postgres_database_url).connect() as connection:
        assert (
            connection.execute(
                text("SELECT count(*) FROM coeus_audit_events WHERE event_type='qc_claimed'")
            ).scalar_one()
            == 1
        )
        audience = connection.execute(
            text(
                "SELECT principal_id FROM coeus_draft_audiences "
                "WHERE product_id=:product AND reason='quality_control'"
            ),
            {"product": product_id},
        ).scalar_one()
        assert audience == winner


def test_postgres_claim_audit_failure_rolls_back_assignment_and_audience(
    postgres_database_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    ticket, product_id = _seed(postgres_database_url)
    reviewer_id = uuid4()
    proposed = replace(
        ticket,
        qc_reviewer_user_id=reviewer_id,
        qc_claimed_at=datetime.now(UTC),
    )

    def fail_audit(*_args: object) -> None:
        raise RuntimeError("synthetic claim audit failure")

    monkeypatch.setattr(PostgresWorkflowTransaction, "_append_audit", fail_audit)
    with pytest.raises(RuntimeError, match="claim audit failure"):
        PostgresWorkflowTransaction(postgres_database_url).commit_ticket_update(
            ticket,
            proposed,
            (WorkflowAuditIntent("qc_claimed", reviewer_id, {}),),
        )

    restored = InMemoryTicketRepository(
        PostgresStateStore(postgres_database_url, "relational")
    ).get(ticket.ticket_id)
    assert restored is not None and restored.qc_reviewer_user_id is None
    with create_engine(postgres_database_url).connect() as connection:
        assert (
            connection.execute(
                text(
                    "SELECT count(*) FROM coeus_draft_audiences "
                    "WHERE product_id=:product AND reason='quality_control'"
                ),
                {"product": product_id},
            ).scalar_one()
            == 0
        )
