from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text

from coeus.domain.enums import TicketState
from coeus.domain.outbox import (
    FailureDisposition,
    OutboxClaimLost,
    OutboxEventNotFound,
    ReplayDisposition,
)
from coeus.domain.tickets import IntakeDetails, TicketRecord
from coeus.persistence.outbox import PostgresOutboxStore
from coeus.persistence.state_store import PostgresStateStore
from coeus.repositories.tickets import InMemoryTicketRepository

pytestmark = pytest.mark.postgres


def _seed_event(database_url: str) -> None:
    repository = InMemoryTicketRepository(PostgresStateStore(database_url, "relational"))
    repository.save(
        TicketRecord(
            ticket_id=uuid4(),
            reference=repository.next_reference(),
            requester_user_id=uuid4(),
            state=TicketState.DRAFT_INTAKE,
            intake=IntakeDetails(title="Synthetic outbox event"),
        )
    )


def test_claims_are_exclusive_and_settlement_is_fenced(postgres_database_url: str) -> None:
    _seed_event(postgres_database_url)
    outbox = PostgresOutboxStore(postgres_database_url)
    first_worker = uuid4()
    message = outbox.claim_pending(first_worker, limit=1, lease_seconds=60)[0]

    assert outbox.claim_pending(uuid4(), limit=1, lease_seconds=60) == ()
    with pytest.raises(OutboxEventNotFound):
        outbox.replay_dead_letter(uuid4())
    with pytest.raises(OutboxClaimLost):
        outbox.mark_delivered(message.event_id, uuid4())
    outbox.mark_delivered(message.event_id, first_worker)
    assert outbox.claim_pending(uuid4(), limit=1, lease_seconds=60) == ()


def test_failures_retry_then_dead_letter_at_the_attempt_limit(
    postgres_database_url: str,
) -> None:
    _seed_event(postgres_database_url)
    outbox = PostgresOutboxStore(postgres_database_url)
    worker = uuid4()
    message = outbox.claim_pending(worker, limit=1, lease_seconds=60)[0]
    first_claim_status = outbox.status()
    assert first_claim_status.pending_count == 1
    assert first_claim_status.retrying_count == 0
    assert (
        outbox.mark_failed(
            message.event_id,
            worker,
            "first failure",
            retry_seconds=1,
            max_attempts=2,
        )
        == FailureDisposition.RETRY_SCHEDULED
    )
    failed_status = outbox.status()
    assert failed_status.pending_count == 1
    assert failed_status.retrying_count == 1

    engine = create_engine(postgres_database_url)
    with engine.begin() as connection:
        connection.execute(
            text("UPDATE coeus_outbox SET available_at = now() WHERE event_id = :event_id"),
            {"event_id": message.event_id},
        )
    retried = outbox.claim_pending(worker, limit=1, lease_seconds=60)[0]
    assert retried.attempt_count == 2
    assert (
        outbox.mark_failed(
            retried.event_id,
            worker,
            "final failure",
            retry_seconds=1,
            max_attempts=2,
        )
        == FailureDisposition.DEAD_LETTERED
    )

    assert outbox.claim_pending(uuid4(), limit=1, lease_seconds=60) == ()
    with engine.connect() as connection:
        row = connection.execute(
            text(
                "SELECT dead_lettered_at IS NOT NULL, last_error "
                "FROM coeus_outbox WHERE event_id = :event_id"
            ),
            {"event_id": message.event_id},
        ).one()
    assert row[0] is True
    assert row[1] == "final failure"

    status = outbox.status()
    assert (status.pending_count, status.retrying_count, status.dead_letter_count) == (0, 0, 1)
    assert status.oldest_pending_age_seconds is None

    assert outbox.replay_dead_letter(message.event_id) == ReplayDisposition.REPLAYED
    assert outbox.replay_dead_letter(message.event_id) == ReplayDisposition.ALREADY_PENDING
    replay_status = outbox.status()
    assert (
        replay_status.pending_count,
        replay_status.retrying_count,
        replay_status.dead_letter_count,
    ) == (1, 0, 0)
    assert replay_status.oldest_pending_age_seconds is not None
    replayed = outbox.claim_pending(worker, limit=1, lease_seconds=60)[0]
    assert replayed.event_id == message.event_id
    assert replayed.attempt_count == 1
    outbox.mark_delivered(replayed.event_id, worker)
    assert outbox.replay_dead_letter(message.event_id) == ReplayDisposition.ALREADY_DELIVERED


def test_concurrent_replay_is_idempotent(postgres_database_url: str) -> None:
    _seed_event(postgres_database_url)
    outbox = PostgresOutboxStore(postgres_database_url)
    worker = uuid4()
    message = outbox.claim_pending(worker, limit=1, lease_seconds=60)[0]
    assert (
        outbox.mark_failed(
            message.event_id,
            worker,
            "synthetic dead letter",
            retry_seconds=1,
            max_attempts=1,
        )
        == FailureDisposition.DEAD_LETTERED
    )

    def replay() -> ReplayDisposition:
        return PostgresOutboxStore(postgres_database_url).replay_dead_letter(message.event_id)

    with ThreadPoolExecutor(max_workers=2) as pool:
        dispositions = tuple(pool.map(lambda _index: replay(), range(2)))

    assert set(dispositions) == {
        ReplayDisposition.REPLAYED,
        ReplayDisposition.ALREADY_PENDING,
    }


def test_expired_claim_cannot_be_settled_by_its_original_worker(
    postgres_database_url: str,
) -> None:
    _seed_event(postgres_database_url)
    outbox = PostgresOutboxStore(postgres_database_url)
    worker = uuid4()
    message = outbox.claim_pending(worker, limit=1, lease_seconds=60)[0]
    engine = create_engine(postgres_database_url)
    with engine.begin() as connection:
        connection.execute(
            text("UPDATE coeus_outbox SET claim_expires_at = now() WHERE event_id = :event_id"),
            {"event_id": message.event_id},
        )

    with pytest.raises(OutboxClaimLost):
        outbox.mark_delivered(message.event_id, worker)
    with pytest.raises(OutboxClaimLost):
        outbox.mark_failed(
            message.event_id,
            worker,
            "stale worker",
            retry_seconds=1,
            max_attempts=2,
        )


def test_invalid_claim_and_retry_settings_fail_before_database_work(
    postgres_database_url: str,
) -> None:
    outbox = PostgresOutboxStore(postgres_database_url)
    with pytest.raises(ValueError, match="positive"):
        outbox.claim_pending(uuid4(), limit=0, lease_seconds=1)
    with pytest.raises(ValueError, match="positive"):
        outbox.mark_failed(uuid4(), uuid4(), "invalid", retry_seconds=0, max_attempts=1)
