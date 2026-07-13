import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text

from coeus.domain.enums import TicketState
from coeus.domain.tickets import IntakeDetails, TicketRecord
from coeus.persistence.codec import encode_value
from coeus.persistence.state_store import PostgresStateStore
from coeus.persistence.ticket_capacity_recovery import recover_ticket_capacity
from coeus.repositories.tickets import InMemoryTicketRepository
from coeus.services.postgres_ticket_admission import PostgresTicketAdmissionController

pytestmark = pytest.mark.postgres


def _ticket(database_url: str) -> TicketRecord:
    repository = InMemoryTicketRepository(PostgresStateStore(database_url, "relational"))
    PostgresTicketAdmissionController(database_url, max_retained=10, max_retained_per_principal=10)
    ticket = TicketRecord(
        ticket_id=uuid4(),
        reference=repository.next_reference(),
        requester_user_id=uuid4(),
        state=TicketState.DRAFT_INTAKE,
        intake=IntakeDetails(title="Capacity recovery"),
    )
    repository.save(ticket)
    return ticket


def test_dry_run_reports_without_writing(postgres_database_url: str) -> None:
    ticket = _ticket(postgres_database_url)
    engine = create_engine(postgres_database_url)
    expired, active, provider = uuid4(), uuid4(), uuid4()
    now = datetime.now(UTC)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO coeus_resource_leases("
                "lease_id,resource_type,principal_id,units,expires_at) "
                "VALUES (:expired,'ticket_creation',:principal,1,:past),"
                "(:active,'ticket_creation',:principal,1,:future),"
                "(:provider,'provider',:principal,1,:past)"
            ),
            {
                "expired": expired,
                "active": active,
                "provider": provider,
                "principal": ticket.requester_user_id,
                "past": now - timedelta(seconds=5),
                "future": now + timedelta(minutes=5),
            },
        )

    report = recover_ticket_capacity(postgres_database_url)

    assert report.retained_count == 1
    assert report.active_lease_ids == (str(active),)
    assert report.expired_lease_ids == (str(expired),)
    with engine.connect() as connection:
        count = connection.execute(text("SELECT count(*) FROM coeus_resource_leases")).scalar_one()
        assert count == 3


def test_expired_cleanup_is_scoped_and_audited(postgres_database_url: str) -> None:
    ticket = _ticket(postgres_database_url)
    engine = create_engine(postgres_database_url)
    expired, active, provider = uuid4(), uuid4(), uuid4()
    now = datetime.now(UTC)
    with engine.begin() as connection:
        for lease_id, resource, expiry in (
            (expired, "ticket_creation", now - timedelta(seconds=5)),
            (active, "ticket_creation", now + timedelta(minutes=5)),
            (provider, "provider", now - timedelta(seconds=5)),
        ):
            connection.execute(
                text(
                    "INSERT INTO coeus_resource_leases("
                    "lease_id,resource_type,principal_id,units,expires_at) "
                    "VALUES (:lease_id,:resource,:principal,1,:expiry)"
                ),
                {
                    "lease_id": lease_id,
                    "resource": resource,
                    "principal": ticket.requester_user_id,
                    "expiry": expiry,
                },
            )

    report = recover_ticket_capacity(
        postgres_database_url,
        action="remove-expired",
        operator="operator-1",
        reason="confirmed stale creation lease",
    )

    assert report.changed_count == 1
    with engine.connect() as connection:
        remaining = set(
            connection.execute(text("SELECT lease_id::text FROM coeus_resource_leases")).scalars()
        )
        assert remaining == {str(active), str(provider)}
        event = connection.execute(text("SELECT event_type FROM coeus_audit_events")).scalar_one()
        assert event == "ticket_capacity_expired_leases_recovered"


def test_projection_repair_uses_validated_payload(postgres_database_url: str) -> None:
    ticket = _ticket(postgres_database_url)
    repository = InMemoryTicketRepository(PostgresStateStore(postgres_database_url, "relational"))
    repository.save_if_current(ticket, replace(ticket, state=TicketState.CANCELLED))
    engine = create_engine(postgres_database_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE coeus_ticket_aggregates SET state='DRAFT_INTAKE', consumes_capacity=true "
                "WHERE ticket_id=:ticket_id"
            ),
            {"ticket_id": ticket.ticket_id},
        )

    report = recover_ticket_capacity(
        postgres_database_url,
        action="repair-projection",
        operator="operator-1",
        reason="repair derived fields",
    )

    assert report.changed_count == 1
    assert report.projection_issues == ()
    assert report.retained_count == 0


def test_projection_repair_rejects_hash_mismatch_atomically(postgres_database_url: str) -> None:
    ticket = _ticket(postgres_database_url)
    engine = create_engine(postgres_database_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE coeus_ticket_aggregates SET "
                "canonical_hash='invalid', consumes_capacity=false "
                "WHERE ticket_id=:ticket_id"
            ),
            {"ticket_id": ticket.ticket_id},
        )

    with pytest.raises(RuntimeError, match="Non-repairable"):
        recover_ticket_capacity(
            postgres_database_url,
            action="repair-projection",
            operator="operator-1",
            reason="repair derived fields",
        )
    with engine.connect() as connection:
        assert (
            connection.execute(
                text("SELECT consumes_capacity FROM coeus_ticket_aggregates")
            ).scalar_one()
            is False
        )


def test_inspection_rejects_a_valid_payload_with_mismatched_aggregate_identity(
    postgres_database_url: str,
) -> None:
    ticket = _ticket(postgres_database_url)
    other = replace(ticket, ticket_id=uuid4())
    payload = encode_value(other)
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    engine = create_engine(postgres_database_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE coeus_ticket_aggregates SET payload=CAST(:payload AS jsonb), "
                "canonical_hash=:digest WHERE ticket_id=:ticket_id"
            ),
            {
                "payload": canonical,
                "digest": sha256(canonical.encode()).hexdigest(),
                "ticket_id": ticket.ticket_id,
            },
        )

    report = recover_ticket_capacity(postgres_database_url)

    assert report.projection_issues[0].reason == "aggregate identity mismatch"
    assert not report.projection_issues[0].repairable


def test_active_lease_release_requires_named_ticket_lease(postgres_database_url: str) -> None:
    ticket = _ticket(postgres_database_url)
    engine = create_engine(postgres_database_url)
    active, provider = uuid4(), uuid4()
    with engine.begin() as connection:
        for lease_id, resource in ((active, "ticket_creation"), (provider, "provider")):
            connection.execute(
                text(
                    "INSERT INTO coeus_resource_leases("
                    "lease_id,resource_type,principal_id,units,expires_at) "
                    "VALUES (:lease_id,:resource,:principal,1,now() + interval '5 minutes')"
                ),
                {
                    "lease_id": lease_id,
                    "resource": resource,
                    "principal": ticket.requester_user_id,
                },
            )

    with pytest.raises(ValueError, match="drained-system"):
        recover_ticket_capacity(
            postgres_database_url,
            action="release-lease",
            lease_id=active,
            operator="operator-1",
            reason="abandoned creator",
        )
    with pytest.raises(ValueError, match="not an active ticket"):
        recover_ticket_capacity(
            postgres_database_url,
            action="release-lease",
            lease_id=provider,
            operator="operator-1",
            reason="wrong resource",
            api_drained=True,
        )
    report = recover_ticket_capacity(
        postgres_database_url,
        action="release-lease",
        lease_id=active,
        operator="operator-1",
        reason="abandoned creator",
        api_drained=True,
    )

    assert report.changed_count == 1
    assert report.active_lease_ids == ()
