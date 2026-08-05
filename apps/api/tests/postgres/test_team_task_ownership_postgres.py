"""Real PostgreSQL tests for workflow-leg team ownership."""

from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

from coeus.domain.team_task_ownership import (
    TeamTaskOwnership,
    TeamTaskOwnershipState,
    WorkflowLeg,
)
from coeus.persistence.team_task_ownership_postgres import (
    PostgresTeamTaskOwnershipRepository,
)

API_ROOT = Path(__file__).resolve().parents[2]
NOW = datetime(2026, 8, 3, 8, tzinfo=UTC)
pytestmark = pytest.mark.postgres


def _upgrade(database_url: str) -> None:
    config = Config(str(API_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "20260803_0019")


def test_create_read_update_and_stale_write(postgres_database_url: str) -> None:
    _upgrade(postgres_database_url)
    engine = create_engine(postgres_database_url)
    unit_id = uuid4()
    revision_id = uuid4()
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO organisation_units"
                "(unit_id,name,short_name,category,parent_unit_id,is_active,valid_from,"
                "valid_until,time_zone,description,version,provenance) VALUES "
                "(:unit_id,'Synthetic Team','Team','delivery_team',NULL,true,:now,NULL,"
                "'Europe/London','',1,'manual')"
            ),
            {"unit_id": unit_id, "now": NOW},
        )
        connection.execute(
            text(
                "INSERT INTO organisation_unit_closure"
                "(ancestor_unit_id,descendant_unit_id,depth) VALUES (:unit_id,:unit_id,0)"
            ),
            {"unit_id": unit_id},
        )
        connection.execute(
            text(
                "INSERT INTO organisation_topology_revisions"
                "(revision_id,unit_id,parent_unit_id,path,valid_from,valid_until,"
                "change_command_id,changed_by_user_id) VALUES "
                "(:revision_id,:unit_id,NULL,:path,:now,NULL,:command_id,:actor_id)"
            ),
            {
                "revision_id": revision_id,
                "unit_id": unit_id,
                "path": [unit_id],
                "now": NOW,
                "command_id": uuid4(),
                "actor_id": uuid4(),
            },
        )
    repository = PostgresTeamTaskOwnershipRepository(engine)
    ownership = TeamTaskOwnership(
        ownership_id=uuid4(),
        ticket_id=uuid4(),
        workflow_leg=WorkflowLeg.CM_COLLECTION,
        owning_unit_id=unit_id,
        manager_user_id=None,
        state=TeamTaskOwnershipState.TRIAGE,
        topology_revision_id=revision_id,
        capability_policy_version=1,
        version=1,
        history_reference=uuid4(),
        provenance="synthetic-test",
        created_at=NOW,
    )
    created = repository.save_ownership(ownership, expected_version=None)
    assert repository.get_ownership(ownership.ticket_id, ownership.workflow_leg) == created
    assert repository.list_unit_ownership(unit_id) == (created,)

    updated = repository.save_ownership(
        replace(ownership, state=TeamTaskOwnershipState.PROPOSED, version=2),
        expected_version=1,
    )
    assert updated.version == 2
    with pytest.raises(ValueError, match="version or identity conflict"):
        repository.save_ownership(replace(ownership, version=2), expected_version=1)
    with pytest.raises(ValueError, match="next expected version"):
        repository.save_ownership(replace(ownership, version=4), expected_version=2)
    with pytest.raises(ValueError, match="between one and 200"):
        repository.list_unit_ownership(unit_id, limit=201)
    engine.dispose()
