"""PostgreSQL evidence for assignment while organisation authority is disabled."""

from dataclasses import replace
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

from coeus.domain.enums import TicketState
from coeus.domain.team_task_ownership import AssignmentOwnershipIntent, WorkflowLeg
from coeus.domain.tickets import IntakeDetails, TicketRecord
from coeus.domain.workflow_transaction import WorkflowAuditIntent
from coeus.persistence.state_store import PostgresStateStore
from coeus.persistence.workflow_transaction import PostgresWorkflowTransaction
from coeus.repositories.tickets import InMemoryTicketRepository

API_ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.postgres


def test_assignment_keeps_legacy_workflow_available_when_organisation_is_disabled(
    postgres_database_url: str,
) -> None:
    """Disabled organisation mode must not require an unconfigured shadow projection."""
    config = Config(str(API_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", postgres_database_url)
    command.upgrade(config, "head")
    actor_id, unit_id = uuid4(), uuid4()
    ticket = TicketRecord(
        uuid4(),
        "TCK-DISABLED-0001",
        uuid4(),
        TicketState.ANALYST_ASSIGNMENT,
        IntakeDetails(title="Synthetic disabled-mode assignment"),
    )
    repository = InMemoryTicketRepository(PostgresStateStore(postgres_database_url, "relational"))
    repository.save(ticket)
    updated = replace(ticket, state=TicketState.ANALYST_IN_PROGRESS)

    transaction = PostgresWorkflowTransaction(
        postgres_database_url,
        canonical_assignment_projection_enabled=False,
    )
    assert transaction.commit_ticket_assignment(
        ticket,
        updated,
        (WorkflowAuditIntent("analyst_assigned", actor_id, {"ticket_id": str(ticket.ticket_id)}),),
        AssignmentOwnershipIntent(unit_id, WorkflowLeg.RFA, actor_id, uuid4()),
    )

    engine = create_engine(postgres_database_url)
    with engine.connect() as connection:
        ownership_count = connection.execute(
            text("SELECT count(*) FROM team_task_ownership")
        ).scalar_one()
        audit_count = connection.execute(
            text("SELECT count(*) FROM coeus_audit_events WHERE event_type='analyst_assigned'")
        ).scalar_one()
    refreshed = InMemoryTicketRepository(PostgresStateStore(postgres_database_url, "relational"))
    assert refreshed.get(ticket.ticket_id).state is TicketState.ANALYST_IN_PROGRESS
    assert ownership_count == 0
    assert audit_count == 1
    engine.dispose()
