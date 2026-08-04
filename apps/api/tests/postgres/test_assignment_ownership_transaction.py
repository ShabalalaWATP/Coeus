"""PostgreSQL evidence for atomic ticket assignment and canonical ownership."""

from dataclasses import replace
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from organisation_account_support import activate_principals
from sqlalchemy import create_engine, text

from coeus.domain.enums import TicketState
from coeus.domain.organisation_bootstrap import OrganisationBootstrapPlan
from coeus.domain.team_task_ownership import AssignmentOwnershipIntent, WorkflowLeg
from coeus.domain.tickets import (
    IntakeDetails,
    TicketRecord,
)
from coeus.domain.workflow_transaction import WorkflowAuditIntent
from coeus.persistence.organisation_bootstrap_postgres import PostgresOrganisationBootstrapStore
from coeus.persistence.state_store import PostgresStateStore
from coeus.persistence.workflow_transaction import PostgresWorkflowTransaction
from coeus.repositories.tickets import InMemoryTicketRepository

API_ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.postgres


def _upgrade(database_url: str) -> None:
    config = Config(str(API_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "head")


def _ticket() -> TicketRecord:
    return TicketRecord(
        uuid4(),
        "TCK-OWN-0001",
        uuid4(),
        TicketState.ANALYST_ASSIGNMENT,
        IntakeDetails(title="Synthetic ownership task", deadline="2026-08-21"),
    )


def test_assignment_commits_ticket_ownership_audit_and_outbox_together(
    postgres_database_url: str,
) -> None:
    _upgrade(postgres_database_url)
    engine = create_engine(postgres_database_url)
    actor_id, unit_id = uuid4(), uuid4()
    result = PostgresOrganisationBootstrapStore(engine).bootstrap(
        OrganisationBootstrapPlan(
            uuid4(), actor_id, unit_id, "Synthetic Team", "SYN", "Europe/London", ""
        )
    )
    activate_principals(engine, actor_id)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO team_delivery_profiles"
                "(profile_id,unit_id,route,wip_limit,weekly_hours,policy_version,"
                "is_active,provenance) "
                "VALUES (:profile,:unit,'rfa',8,40,3,true,'synthetic-test')"
            ),
            {"profile": uuid4(), "unit": unit_id},
        )
    ticket = _ticket()
    repository = InMemoryTicketRepository(PostgresStateStore(postgres_database_url, "relational"))
    repository.save(ticket)
    updated = replace(ticket, state=TicketState.ANALYST_IN_PROGRESS)
    intent = AssignmentOwnershipIntent(unit_id, WorkflowLeg.RFA, actor_id, uuid4())
    transaction = PostgresWorkflowTransaction(postgres_database_url)
    assert transaction.commit_ticket_assignment(
        ticket,
        updated,
        (WorkflowAuditIntent("analyst_assigned", actor_id, {"ticket_id": str(ticket.ticket_id)}),),
        intent,
    )
    with engine.connect() as connection:
        row = connection.execute(text("SELECT * FROM team_task_ownership")).mappings().one()
        event = (
            connection.execute(
                text(
                    "SELECT event_type,payload FROM coeus_outbox "
                    "WHERE event_type='team_task_ownership_changed'"
                )
            )
            .mappings()
            .one()
        )
        audit_count = connection.execute(
            text("SELECT count(*) FROM coeus_audit_events WHERE event_type='analyst_assigned'")
        ).scalar_one()
    assert row["owning_unit_id"] == unit_id
    assert row["topology_revision_id"] == result.topology_revision_id
    assert row["capability_policy_version"] == 3
    assert row["state"] == "active" and row["version"] == 1
    assert event["event_type"] == "team_task_ownership_changed"
    assert event["payload"]["ownership_version"] == "1"
    assert audit_count == 1
    refreshed = InMemoryTicketRepository(PostgresStateStore(postgres_database_url, "relational"))
    assert refreshed.get(ticket.ticket_id).state is TicketState.ANALYST_IN_PROGRESS
    engine.dispose()


def test_assignment_rolls_back_when_delivery_authority_is_not_current(
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
    activate_principals(engine, actor_id)
    ticket = _ticket()
    repository = InMemoryTicketRepository(PostgresStateStore(postgres_database_url, "relational"))
    repository.save(ticket)
    with engine.connect() as connection:
        initial_audits = connection.execute(
            text("SELECT count(*) FROM coeus_audit_events")
        ).scalar_one()
    with pytest.raises(ValueError, match="delivery authority"):
        PostgresWorkflowTransaction(postgres_database_url).commit_ticket_assignment(
            ticket,
            replace(ticket, state=TicketState.ANALYST_IN_PROGRESS),
            (
                WorkflowAuditIntent(
                    "analyst_assigned", actor_id, {"ticket_id": str(ticket.ticket_id)}
                ),
            ),
            AssignmentOwnershipIntent(unit_id, WorkflowLeg.RFA, actor_id, uuid4()),
        )
    assert repository.get(ticket.ticket_id) == ticket
    with engine.connect() as connection:
        ownership_count = connection.execute(
            text("SELECT count(*) FROM team_task_ownership")
        ).scalar_one()
        audit_count = connection.execute(
            text("SELECT count(*) FROM coeus_audit_events")
        ).scalar_one()
        assert ownership_count == 0
        assert audit_count == initial_audits
    engine.dispose()
