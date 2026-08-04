"""PostgreSQL evidence for direct-team board authority and projection."""

from datetime import UTC, date, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from organisation_account_support import activate_principals
from sqlalchemy import create_engine

from coeus.domain.enums import TicketState
from coeus.domain.organisation_bootstrap import OrganisationBootstrapPlan
from coeus.domain.team_task_board import TeamBoardColumn, TeamTaskBoardDenied
from coeus.domain.team_task_ownership import (
    TeamTaskOwnership,
    TeamTaskOwnershipState,
    WorkflowLeg,
)
from coeus.domain.tickets import IntakeDetails, TicketRecord
from coeus.persistence.organisation_bootstrap_postgres import PostgresOrganisationBootstrapStore
from coeus.persistence.state_store import PostgresStateStore
from coeus.persistence.team_task_board_postgres import PostgresTeamTaskBoardStore
from coeus.persistence.team_task_ownership_postgres import PostgresTeamTaskOwnershipRepository
from coeus.repositories.tickets import InMemoryTicketRepository

API_ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.postgres


def _upgrade(database_url: str) -> None:
    config = Config(str(API_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "head")


def test_board_requires_exact_current_task_grant_and_returns_allowlisted_card(
    postgres_database_url: str,
) -> None:
    _upgrade(postgres_database_url)
    engine = create_engine(postgres_database_url)
    actor_id, unit_id, ticket_id = uuid4(), uuid4(), uuid4()
    foundation = PostgresOrganisationBootstrapStore(engine).bootstrap(
        OrganisationBootstrapPlan(
            uuid4(), actor_id, unit_id, "Synthetic Team", "SYN", "Europe/London", ""
        )
    )
    activate_principals(engine, actor_id)
    ticket = TicketRecord(
        ticket_id,
        "TCK-BOARD-001",
        uuid4(),
        TicketState.ANALYST_IN_PROGRESS,
        IntakeDetails(
            title="Synthetic board task",
            description="Must not appear in the board response.",
            priority="High",
        ),
    )
    InMemoryTicketRepository(PostgresStateStore(postgres_database_url, "relational")).save(ticket)
    PostgresTeamTaskOwnershipRepository(engine).save_ownership(
        TeamTaskOwnership(
            uuid4(),
            ticket_id,
            WorkflowLeg.RFA,
            unit_id,
            actor_id,
            TeamTaskOwnershipState.ACTIVE,
            foundation.topology_revision_id,
            1,
            1,
            uuid4(),
            "synthetic-test",
            datetime.now(UTC),
            datetime.now(UTC),
            date(2026, 8, 21),
        ),
        expected_version=None,
    )
    store = PostgresTeamTaskBoardStore(engine)

    board = store.get_board(actor_id, unit_id, include_completed=False, limit=50)

    assert len(board.cards) == 1 and not board.truncated
    card = board.cards[0]
    assert card.column is TeamBoardColumn.IN_PROGRESS
    assert card.reference == "TCK-BOARD-001" and card.title == "Synthetic board task"
    assert not hasattr(card, "description") and not hasattr(card, "requester_user_id")
    with pytest.raises(TeamTaskBoardDenied):
        store.get_board(uuid4(), unit_id, include_completed=False, limit=50)
    with pytest.raises(ValueError, match="between one and 100"):
        store.get_board(actor_id, unit_id, include_completed=False, limit=101)
    engine.dispose()
