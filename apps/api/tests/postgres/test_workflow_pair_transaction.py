from dataclasses import replace
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text

from coeus.domain.enums import TicketState
from coeus.domain.tickets import IntakeDetails, TicketRecord
from coeus.domain.workflow_transaction import WorkflowAuditIntent
from coeus.persistence.state_store import PostgresStateStore
from coeus.persistence.workflow_transaction import PostgresWorkflowTransaction
from coeus.repositories.tickets import InMemoryTicketRepository

pytestmark = pytest.mark.postgres


def _ticket(reference: str) -> TicketRecord:
    return TicketRecord(
        ticket_id=uuid4(),
        reference=reference,
        requester_user_id=uuid4(),
        state=TicketState.QC_REVIEW,
        intake=IntakeDetails(title="Synthetic paired transaction"),
    )


def _seed(database_url: str) -> tuple[TicketRecord, TicketRecord]:
    first = _ticket("TCK-PAIR-0001")
    second = _ticket("TCK-PAIR-0002")
    repository = InMemoryTicketRepository(PostgresStateStore(database_url, "relational"))
    repository.save(first)
    repository.save(second)
    return first, second


def _audit(first: TicketRecord, second: TicketRecord) -> WorkflowAuditIntent:
    return WorkflowAuditIntent(
        "tickets_linked",
        first.requester_user_id,
        {"ticket_id": str(first.ticket_id), "related_ticket_id": str(second.ticket_id)},
    )


def test_ticket_pair_commits_symmetric_links_and_audit_as_one_unit(
    postgres_database_url: str,
) -> None:
    first, second = _seed(postgres_database_url)
    first_updated = replace(first, related_ticket_ids=(second.ticket_id,))
    second_updated = replace(second, related_ticket_ids=(first.ticket_id,))

    assert PostgresWorkflowTransaction(postgres_database_url).commit_ticket_pair(
        (first, second), (first_updated, second_updated), (_audit(first, second),)
    )

    restored = InMemoryTicketRepository(PostgresStateStore(postgres_database_url, "relational"))
    assert restored.get(first.ticket_id) == first_updated
    assert restored.get(second.ticket_id) == second_updated


def test_ticket_pair_conflict_leaves_both_aggregates_and_audit_unchanged(
    postgres_database_url: str,
) -> None:
    first, second = _seed(postgres_database_url)
    stale_second = replace(second, state=TicketState.INFO_REQUIRED)

    assert not PostgresWorkflowTransaction(postgres_database_url).commit_ticket_pair(
        (first, stale_second),
        (
            replace(first, related_ticket_ids=(second.ticket_id,)),
            replace(second, related_ticket_ids=(first.ticket_id,)),
        ),
        (_audit(first, second),),
    )

    restored = InMemoryTicketRepository(PostgresStateStore(postgres_database_url, "relational"))
    assert restored.get(first.ticket_id) == first
    assert restored.get(second.ticket_id) == second
    engine = create_engine(postgres_database_url)
    with engine.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM coeus_audit_events")).scalar_one() == 0


def test_ticket_pair_rejects_identity_changes_and_duplicate_aggregates(
    postgres_database_url: str,
) -> None:
    first, second = _seed(postgres_database_url)
    transaction = PostgresWorkflowTransaction(postgres_database_url)

    with pytest.raises(ValueError, match="identities"):
        transaction.commit_ticket_pair(
            (first, second), (first, _ticket("TCK-PAIR-0003")), (_audit(first, second),)
        )
    with pytest.raises(ValueError, match="identities"):
        transaction.commit_ticket_pair(
            (first, first), (first, first), (_audit(first, second),)
        )


def test_ticket_pair_rolls_back_both_aggregates_when_audit_fails(
    postgres_database_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    first, second = _seed(postgres_database_url)

    def fail_audit(*_args: object) -> None:
        raise RuntimeError("synthetic pair audit failure")

    monkeypatch.setattr(PostgresWorkflowTransaction, "_append_audit", fail_audit)
    with pytest.raises(RuntimeError, match="pair audit failure"):
        PostgresWorkflowTransaction(postgres_database_url).commit_ticket_pair(
            (first, second),
            (
                replace(first, related_ticket_ids=(second.ticket_id,)),
                replace(second, related_ticket_ids=(first.ticket_id,)),
            ),
            (_audit(first, second),),
        )

    restored = InMemoryTicketRepository(PostgresStateStore(postgres_database_url, "relational"))
    assert restored.get(first.ticket_id) == first
    assert restored.get(second.ticket_id) == second
