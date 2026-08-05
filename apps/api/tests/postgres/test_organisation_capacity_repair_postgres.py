"""Real PostgreSQL evidence for bounded Sprint 24 repair tooling."""

from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError

from coeus.domain.enums import TicketState
from coeus.domain.organisation_bootstrap import OrganisationBootstrapPlan
from coeus.domain.tickets import IntakeDetails, TicketRecord
from coeus.persistence.organisation_bootstrap_postgres import PostgresOrganisationBootstrapStore
from coeus.persistence.organisation_capacity_repair import (
    _repair_reservations,
    inspect_or_repair_organisation_capacity,
)
from coeus.persistence.state_store import PostgresStateStore
from coeus.repositories.tickets import InMemoryTicketRepository

API_ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.postgres


def _upgrade(database_url: str) -> None:
    config = Config(str(API_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "head")


def _seed(database_url: str) -> tuple[UUID, UUID, UUID, UUID]:
    _upgrade(database_url)
    engine = create_engine(database_url)
    operator_id, user_id, unit_id = uuid4(), uuid4(), uuid4()
    PostgresOrganisationBootstrapStore(engine).bootstrap(
        OrganisationBootstrapPlan(
            uuid4(), operator_id, unit_id, "Synthetic Repair Team", "SRT", "Europe/London", ""
        )
    )
    repository = InMemoryTicketRepository(PostgresStateStore(database_url, "relational"))
    ticket = TicketRecord(
        uuid4(),
        repository.next_reference(),
        uuid4(),
        TicketState.DRAFT_INTAKE,
        IntakeDetails(title="Synthetic repair evidence"),
    )
    repository.save(ticket)
    package_id, reservation_id, now = uuid4(), uuid4(), datetime.now(UTC)
    with engine.begin() as connection:
        revision_id = connection.execute(
            text(
                "SELECT revision_id FROM organisation_topology_revisions "
                "WHERE unit_id=:unit_id ORDER BY valid_from DESC LIMIT 1"
            ),
            {"unit_id": unit_id},
        ).scalar_one()
        connection.execute(
            text(_OWNERSHIP),
            {
                "ownership_id": uuid4(),
                "ticket_id": ticket.ticket_id,
                "unit_id": unit_id,
                "revision_id": revision_id,
                "history_reference": uuid4(),
                "now": now,
            },
        )
        connection.execute(
            text(_PACKAGE),
            {
                "package_id": package_id,
                "ticket_id": ticket.ticket_id,
                "unit_id": unit_id,
                "user_id": user_id,
                "now": now,
            },
        )
        _insert_reservations(
            connection,
            package_id,
            ticket.ticket_id,
            user_id,
            now,
            ((reservation_id, "primary-reservation"),),
        )
    engine.dispose()
    return operator_id, user_id, package_id, reservation_id


def _insert_reservations(
    connection,  # type: ignore[no-untyped-def]
    package_id: UUID,
    ticket_id: UUID,
    user_id: UUID,
    now: datetime,
    identities: tuple[tuple[UUID, str], ...],
) -> None:
    connection.execute(
        text(_RESERVATION),
        [
            {
                "reservation_id": reservation_id,
                "package_id": package_id,
                "ticket_id": ticket_id,
                "user_id": user_id,
                "key": key,
                "now": now,
            }
            for reservation_id, key in identities
        ],
    )


def test_real_postgres_inspection_repair_and_fail_closed_guards(
    postgres_database_url: str,
) -> None:
    operator_id, user_id, package_id, reservation_id = _seed(postgres_database_url)
    engine = create_engine(postgres_database_url)

    before = inspect_or_repair_organisation_capacity(postgres_database_url)
    assert before.topology_issues == before.ownership_issues == ()
    assert [issue.code for issue in before.reservation_issues] == ["terminal_package_reservation"]
    with engine.connect() as connection:
        assert connection.execute(text(_STATE), {"id": reservation_id}).one() == ("active", 1)
        assert _evidence_count(connection) == (0, 0)

    repaired = inspect_or_repair_organisation_capacity(
        postgres_database_url,
        action="repair-reservations",
        operator_user_id=operator_id,
        reason="Reviewed synthetic terminal reservation",
        reviewed=True,
    )
    repeated = inspect_or_repair_organisation_capacity(
        postgres_database_url,
        action="repair-reservations",
        operator_user_id=operator_id,
        reason="Reviewed synthetic terminal reservation",
        reviewed=True,
    )
    assert repaired.changed_count == 1 and not repaired.has_issues
    assert repeated.changed_count == 0 and not repeated.has_issues
    with engine.connect() as connection:
        assert connection.execute(text(_STATE), {"id": reservation_id}).one() == ("released", 2)
        assert _evidence_count(connection) == (1, 1)

    _prove_mismatch_and_stale_recheck(engine, postgres_database_url, user_id, reservation_id)
    _prove_truncation_refusal(engine, postgres_database_url, operator_id, package_id)
    _prove_audit_failure_rolls_back(engine, postgres_database_url, operator_id, reservation_id)
    engine.dispose()


def _prove_mismatch_and_stale_recheck(
    engine,
    database_url: str,
    user_id: UUID,
    reservation_id: UUID,  # type: ignore[no-untyped-def]
) -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE capacity_reservations SET state='active',user_id=:user "
                "WHERE reservation_id=:id"
            ),
            {"id": reservation_id, "user": uuid4()},
        )
    mismatch = inspect_or_repair_organisation_capacity(database_url)
    assert mismatch.reservation_issues[0].code == "reservation_package_mismatch"
    with pytest.raises(RuntimeError, match="manual disposition"):
        inspect_or_repair_organisation_capacity(
            database_url,
            action="repair-reservations",
            operator_user_id=uuid4(),
            reason="Must refuse mismatched authority evidence",
            reviewed=True,
        )
    with engine.begin() as connection:
        connection.execute(
            text("UPDATE capacity_reservations SET user_id=:user WHERE reservation_id=:id"),
            {"id": reservation_id, "user": user_id},
        )
    stale_issue = inspect_or_repair_organisation_capacity(database_url).reservation_issues[0]
    with engine.begin() as connection:
        connection.execute(
            text("UPDATE capacity_reservations SET state='released' WHERE reservation_id=:id"),
            {"id": reservation_id},
        )
    with engine.begin() as connection:
        assert _repair_reservations(connection, (stale_issue,)) == ()


def _prove_truncation_refusal(
    engine,
    database_url: str,
    operator_id: UUID,
    package_id: UUID,  # type: ignore[no-untyped-def]
) -> None:
    now = datetime.now(UTC)
    with engine.begin() as connection:
        package = connection.execute(
            text(
                "SELECT ticket_id,accountable_user_id FROM canonical_work_packages "
                "WHERE package_id=:id"
            ),
            {"id": package_id},
        ).one()
        identities = tuple((uuid4(), f"overflow-{index}") for index in range(501))
        _insert_reservations(
            connection, package_id, package.ticket_id, package.accountable_user_id, now, identities
        )
    report = inspect_or_repair_organisation_capacity(database_url)
    assert report.truncated and len(report.reservation_issues) == 500
    with pytest.raises(RuntimeError, match="truncated"):
        inspect_or_repair_organisation_capacity(
            database_url,
            action="repair-reservations",
            operator_user_id=operator_id,
            reason="Bounded preview cannot authorise overflow repair",
            reviewed=True,
        )
    with engine.begin() as connection:
        active = connection.execute(
            text("SELECT count(*) FROM capacity_reservations WHERE state='active'")
        ).scalar_one()
        assert active == 501
        connection.execute(
            text("DELETE FROM capacity_reservations WHERE idempotency_key LIKE 'overflow-%'")
        )


def _prove_audit_failure_rolls_back(
    engine,
    database_url: str,
    operator_id: UUID,
    reservation_id: UUID,  # type: ignore[no-untyped-def]
) -> None:
    with engine.begin() as connection:
        connection.execute(
            text("UPDATE capacity_reservations SET state='active' WHERE reservation_id=:id"),
            {"id": reservation_id},
        )
        connection.execute(text(_REJECT_AUDIT_FUNCTION))
        connection.execute(text(_REJECT_AUDIT_TRIGGER))
    with pytest.raises(DBAPIError, match="synthetic audit failure"):
        inspect_or_repair_organisation_capacity(
            database_url,
            action="repair-reservations",
            operator_user_id=operator_id,
            reason="Synthetic audit rollback proof",
            reviewed=True,
        )
    with engine.connect() as connection:
        assert connection.execute(text(_STATE), {"id": reservation_id}).one() == ("active", 2)
        assert _evidence_count(connection) == (1, 1)


def _evidence_count(connection) -> tuple[int, int]:  # type: ignore[no-untyped-def]
    audit = connection.execute(
        text("SELECT count(*) FROM coeus_audit_events WHERE event_type=:event"),
        {"event": "capacity_reservation_drift_repaired"},
    ).scalar_one()
    outbox = connection.execute(
        text("SELECT count(*) FROM coeus_outbox WHERE event_type=:event"),
        {"event": "capacity_reservation_drift_repaired"},
    ).scalar_one()
    return int(audit), int(outbox)


_OWNERSHIP = """
INSERT INTO team_task_ownership(
 ownership_id,ticket_id,workflow_leg,owning_unit_id,state,accepted_at,target_date,
 topology_revision_id,capability_policy_version,version,history_reference,provenance,created_at)
VALUES (
 :ownership_id,:ticket_id,'rfa',:unit_id,'active',:now,NULL,
 :revision_id,1,1,:history_reference,'synthetic-repair-test',:now)
"""

_PACKAGE = """
INSERT INTO canonical_work_packages(
 package_id,ticket_id,workflow_leg,owning_unit_id,accountable_user_id,title,state,
 estimated_minutes,remaining_minutes,sort_order,version,provenance,created_at,updated_at)
VALUES (
 :package_id,:ticket_id,'rfa',:unit_id,:user_id,'Synthetic terminal package','complete',
 60,0,0,1,'synthetic-repair-test',:now,:now)
"""

_RESERVATION = """
INSERT INTO capacity_reservations(
 reservation_id,user_id,ticket_id,workflow_leg,package_id,starts_at,ends_at,reserved_minutes,
 state,expires_at,idempotency_key,request_hash,actor_user_id,version,created_at,updated_at)
VALUES (
 :reservation_id,:user_id,:ticket_id,'rfa',:package_id,:now,:now + interval '1 hour',15,
 'active',NULL,:key,repeat('a',64),:user_id,1,:now,:now)
"""

_STATE = "SELECT state,version FROM capacity_reservations WHERE reservation_id=:id"

_REJECT_AUDIT_FUNCTION = """
CREATE OR REPLACE FUNCTION reject_synthetic_capacity_repair_audit()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.event_type='capacity_reservation_drift_repaired' THEN
    RAISE EXCEPTION 'synthetic audit failure';
  END IF;
  RETURN NEW;
END
$$
"""

_REJECT_AUDIT_TRIGGER = """
CREATE TRIGGER reject_synthetic_capacity_repair_audit
BEFORE INSERT ON coeus_audit_events
FOR EACH ROW EXECUTE FUNCTION reject_synthetic_capacity_repair_audit()
"""
