"""PostgreSQL evidence for safe historical assignment ownership reconciliation."""

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

from coeus.domain.enums import TicketState
from coeus.domain.organisation_bootstrap import OrganisationBootstrapPlan
from coeus.domain.tickets import AnalystAssignment, IntakeDetails, RoutingRoute, TicketRecord
from coeus.persistence.organisation_bootstrap_postgres import PostgresOrganisationBootstrapStore
from coeus.persistence.state_store import PostgresStateStore
from coeus.persistence.task_ownership_reconciliation_postgres import (
    PostgresTaskOwnershipReconciliationStore,
)
from coeus.repositories.tickets import InMemoryTicketRepository

API_ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.postgres


def _upgrade(database_url: str) -> None:
    config = Config(str(API_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "20260803_0028")


def _ticket(*team_ids) -> TicketRecord:  # type: ignore[no-untyped-def]
    ticket_id, actor_id, now = uuid4(), uuid4(), datetime.now(UTC)
    assignments = tuple(
        AnalystAssignment(
            uuid4(), ticket_id, uuid4(), actor_id, RoutingRoute.RFA, now, team_id, "Synthetic"
        )
        for team_id in team_ids
    )
    return TicketRecord(
        ticket_id,
        f"TCK-{str(ticket_id)[:8]}",
        uuid4(),
        TicketState.ANALYST_IN_PROGRESS,
        IntakeDetails(title="Synthetic historical assignment", deadline="2026-08-21"),
        analyst_assignments=assignments,
    )


def test_reconciliation_backfills_only_unambiguous_current_delivery_ownership(
    postgres_database_url: str,
) -> None:
    _upgrade(postgres_database_url)
    engine = create_engine(postgres_database_url)
    actor_id, unit_id = uuid4(), uuid4()
    PostgresOrganisationBootstrapStore(engine).bootstrap(
        OrganisationBootstrapPlan(
            uuid4(), actor_id, unit_id, "Synthetic Team", "SYN", "Europe/London", ""
        )
    )
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO team_delivery_profiles"
                "(profile_id,unit_id,route,wip_limit,weekly_hours,policy_version,"
                "is_active,provenance) "
                "VALUES (:profile,:unit,'rfa',8,40,2,true,'synthetic-test')"
            ),
            {"profile": uuid4(), "unit": unit_id},
        )
    tickets = (_ticket(unit_id), _ticket(unit_id, uuid4()), _ticket(None))
    repository = InMemoryTicketRepository(PostgresStateStore(postgres_database_url, "relational"))
    for ticket in tickets:
        repository.save(ticket)
    store = PostgresTaskOwnershipReconciliationStore(engine)

    result = store.reconcile()
    repeated = store.reconcile()

    assert result.scanned_tickets == 3
    assert result.created_ownerships == 1 and result.findings == 2
    assert repeated.already_applied and repeated.checkpoint_id == result.checkpoint_id
    with engine.connect() as connection:
        owners = connection.execute(text("SELECT * FROM team_task_ownership")).mappings().all()
        findings = (
            connection.execute(
                text(
                    "SELECT finding_code FROM organisation_reconciliation_findings "
                    "ORDER BY finding_code"
                )
            )
            .scalars()
            .all()
        )
        audits = connection.execute(
            text(
                "SELECT count(*) FROM coeus_audit_events "
                "WHERE event_type='task_ownership_reconciled'"
            )
        ).scalar_one()
    assert len(owners) == 1 and owners[0]["owning_unit_id"] == unit_id
    assert owners[0]["provenance"] == "legacy-ticket-assignment-ownership-v1"
    assert findings == ["ownership_ambiguous", "ownership_ambiguous"]
    assert audits == 1
    engine.dispose()
