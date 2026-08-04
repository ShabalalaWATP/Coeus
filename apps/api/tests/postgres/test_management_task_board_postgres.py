"""PostgreSQL proof for descendant detail, paging and privacy-safe aggregates."""

from datetime import UTC, date, datetime
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from organisation_account_support import activate_principals
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from coeus.domain.enums import TicketState
from coeus.domain.organisation_bootstrap import OrganisationBootstrapPlan
from coeus.domain.team_task_board import TeamBoardQuery, TeamBoardScope, TeamTaskBoardDenied
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


def test_management_board_separates_detail_from_aggregate_authority(
    postgres_database_url: str,
) -> None:
    config = Config(str(API_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", postgres_database_url)
    command.upgrade(config, "head")
    engine = create_engine(postgres_database_url)
    bootstrap_actor, manager_id, root_id, child_id = uuid4(), uuid4(), uuid4(), uuid4()
    foundation = PostgresOrganisationBootstrapStore(engine).bootstrap(
        OrganisationBootstrapPlan(
            uuid4(), bootstrap_actor, root_id, "Root Team", "ROOT", "Europe/London", ""
        )
    )
    activate_principals(engine, bootstrap_actor, manager_id)
    child_revision = _create_child_and_grants(engine, manager_id, root_id, child_id)
    root_tickets = [
        _write_ticket(
            engine,
            postgres_database_url,
            root_id,
            foundation.topology_revision_id,
            manager_id,
            index,
        )
        for index in (1, 2)
    ]
    child_ticket = _write_ticket(
        engine, postgres_database_url, child_id, child_revision, manager_id, 3
    )
    store = PostgresTeamTaskBoardStore(engine)

    first = store.get_board(
        manager_id,
        root_id,
        TeamBoardQuery(scope=TeamBoardScope.DESCENDANTS, limit=1),
    )
    assert len(first.cards) == 1 and first.next_cursor and first.truncated
    assert first.cards[0].ticket_id in root_tickets
    assert first.cards[0].unit_id == root_id
    assert [(item.unit_id, item.count, item.suppressed) for item in first.aggregates] == [
        (child_id, None, True)
    ]
    assert all(
        not hasattr(item, "reference") and not hasattr(item, "title") for item in first.aggregates
    )

    second = store.get_board(
        manager_id,
        root_id,
        TeamBoardQuery(
            scope=TeamBoardScope.DESCENDANTS,
            cursor=first.next_cursor,
            limit=1,
        ),
    )
    assert len(second.cards) == 1
    assert second.cards[0].ticket_id in root_tickets
    assert second.cards[0].ticket_id != first.cards[0].ticket_id
    aggregate_only = store.get_board(
        manager_id,
        root_id,
        TeamBoardQuery(scope=TeamBoardScope.DESCENDANTS, unit_ids=(child_id,)),
    )
    assert aggregate_only.cards == ()
    assert aggregate_only.aggregates[0].count is None
    assert aggregate_only.aggregates[0].suppressed
    assert child_ticket not in {card.ticket_id for card in first.cards + second.cards}
    with pytest.raises(TeamTaskBoardDenied):
        store.get_board(
            manager_id,
            root_id,
            TeamBoardQuery(scope=TeamBoardScope.DESCENDANTS, unit_ids=(uuid4(),)),
        )
    engine.dispose()


def _create_child_and_grants(
    engine: Engine, manager_id: UUID, root_id: UUID, child_id: UUID
) -> UUID:
    now, revision_id = datetime.now(UTC), uuid4()
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO organisation_units"
                "(unit_id,name,short_name,category,parent_unit_id,is_active,valid_from,"
                "time_zone,description,provenance,version) VALUES "
                "(:id,'Restricted Child','CHILD','delivery_team',:root,true,:at,"
                "'Europe/London','','test',1)"
            ),
            {"id": child_id, "root": root_id, "at": now},
        )
        connection.execute(
            text(
                "INSERT INTO organisation_unit_closure"
                "(ancestor_unit_id,descendant_unit_id,depth) VALUES "
                "(:child,:child,0),(:root,:child,1)"
            ),
            {"child": child_id, "root": root_id},
        )
        connection.execute(
            text(
                "INSERT INTO organisation_topology_revisions"
                "(revision_id,unit_id,parent_unit_id,path,valid_from,change_command_id,"
                "changed_by_user_id) VALUES (:revision,:child,:root,:path,:at,:command,:actor)"
            ),
            {
                "revision": revision_id,
                "child": child_id,
                "root": root_id,
                "path": [root_id, child_id],
                "at": now,
                "command": uuid4(),
                "actor": manager_id,
            },
        )
        for action, descendants in (("task:view", False), ("organisation:view_aggregate", True)):
            connection.execute(
                text(
                    "INSERT INTO team_management_grants"
                    "(grant_id,manager_user_id,root_unit_id,action,include_descendants,"
                    "valid_from,created_by_user_id,reason,delegation_depth,version) VALUES "
                    "(:grant,:actor,:root,:action,:descendants,:at,:actor,'test',0,1)"
                ),
                {
                    "grant": uuid4(),
                    "actor": manager_id,
                    "root": root_id,
                    "action": action,
                    "descendants": descendants,
                    "at": now,
                },
            )
    return revision_id


def _write_ticket(
    engine: Engine,
    database_url: str,
    unit_id: UUID,
    revision_id: UUID,
    manager_id: UUID,
    index: int,
) -> UUID:
    ticket_id = uuid4()
    ticket = TicketRecord(
        ticket_id,
        f"TCK-MGMT-{index:03d}",
        uuid4(),
        TicketState.ANALYST_IN_PROGRESS,
        IntakeDetails(title=f"Synthetic task {index}", priority="Routine"),
    )
    InMemoryTicketRepository(PostgresStateStore(database_url, "relational")).save(ticket)
    PostgresTeamTaskOwnershipRepository(engine).save_ownership(
        TeamTaskOwnership(
            uuid4(),
            ticket_id,
            WorkflowLeg.RFA,
            unit_id,
            manager_id,
            TeamTaskOwnershipState.ACTIVE,
            revision_id,
            1,
            1,
            uuid4(),
            "test",
            datetime.now(UTC),
            datetime.now(UTC),
            date(2026, 8, 21),
        ),
        expected_version=None,
    )
    return ticket_id
