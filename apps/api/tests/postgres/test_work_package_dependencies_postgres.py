"""Real PostgreSQL evidence for reviewed dependency commands."""

from dataclasses import replace
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
from coeus.domain.work_package_dependencies import (
    ChangeDependencyCommand,
    DependencyChangeRequest,
    DependencyOperation,
    WorkPackageDependencyConflict,
)
from coeus.persistence.organisation_bootstrap_postgres import PostgresOrganisationBootstrapStore
from coeus.persistence.state_store import PostgresStateStore
from coeus.persistence.work_package_dependencies_postgres import (
    PostgresWorkPackageDependencyStore,
)
from coeus.repositories.tickets import InMemoryTicketRepository

API_ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.postgres


def _upgrade(database_url: str) -> None:
    config = Config(str(API_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "20260804_0034")


def _evidence(database_url: str) -> tuple[UUID, DependencyChangeRequest]:
    engine = create_engine(database_url)
    actor_id, unit_id, owner_id = uuid4(), uuid4(), uuid4()
    topology = PostgresOrganisationBootstrapStore(engine).bootstrap(
        OrganisationBootstrapPlan(
            uuid4(), actor_id, unit_id, "Synthetic RFA Team", "SYN-RFA", "Europe/London", ""
        )
    )
    ticket = TicketRecord(
        uuid4(),
        "TCK-DEPEND-0001",
        uuid4(),
        TicketState.ANALYST_IN_PROGRESS,
        IntakeDetails(title="Synthetic dependency task"),
    )
    InMemoryTicketRepository(PostgresStateStore(database_url, "relational")).save(ticket)
    package_id, predecessor_id, grant_id = uuid4(), uuid4(), uuid4()
    now = datetime.now(UTC)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO identity_account_projection"
                "(user_id,is_active,roles,credential_version,source_hash) "
                "VALUES (:actor,true,ARRAY['Administrator'],1,:source_hash)"
            ),
            {"actor": actor_id, "source_hash": "a" * 64},
        )
        connection.execute(
            text(
                "INSERT INTO team_management_grants"
                "(grant_id,manager_user_id,root_unit_id,action,include_descendants,valid_from,"
                "created_by_user_id,reason,version) VALUES "
                "(:grant,:actor,:unit,'task:assign',false,:now,:actor,'Synthetic grant',4)"
            ),
            {"grant": grant_id, "actor": actor_id, "unit": unit_id, "now": now},
        )
        connection.execute(
            text(
                "INSERT INTO team_task_ownership"
                "(ownership_id,ticket_id,workflow_leg,owning_unit_id,manager_user_id,state,"
                "accepted_at,topology_revision_id,capability_policy_version,version,"
                "history_reference,provenance,reason,created_at) VALUES "
                "(:ownership,:ticket,'rfa',:unit,:actor,'active',:now,:topology,1,2,"
                ":history,'test','Synthetic ownership',:now)"
            ),
            {
                "ownership": uuid4(),
                "ticket": ticket.ticket_id,
                "unit": unit_id,
                "actor": actor_id,
                "now": now,
                "topology": topology.topology_revision_id,
                "history": uuid4(),
            },
        )
        connection.execute(
            text(
                "INSERT INTO canonical_work_packages"
                "(package_id,ticket_id,workflow_leg,owning_unit_id,accountable_user_id,title,"
                "state,sort_order,version,provenance,created_at,updated_at) VALUES "
                "(:package,:ticket,'rfa',:unit,:owner,'Synthetic dependent','ready',0,1,"
                "'test',:now,:now),"
                "(:predecessor,:ticket,'rfa',:unit,:owner,'Synthetic predecessor','ready',1,1,"
                "'test',:now,:now)"
            ),
            {
                "package": package_id,
                "predecessor": predecessor_id,
                "ticket": ticket.ticket_id,
                "unit": unit_id,
                "owner": owner_id,
                "now": now,
            },
        )
    engine.dispose()
    return actor_id, DependencyChangeRequest(
        unit_id,
        package_id,
        predecessor_id,
        DependencyOperation.ADD,
        1,
        1,
        2,
        grant_id,
        4,
    )


def test_add_replay_remove_cycle_and_immutable_evidence(postgres_database_url: str) -> None:
    _upgrade(postgres_database_url)
    actor_id, request = _evidence(postgres_database_url)
    engine = create_engine(postgres_database_url)
    store = PostgresWorkPackageDependencyStore(engine)
    preview = store.preview(actor_id, request)
    command_id = uuid4()
    add = ChangeDependencyCommand(
        command_id, "dependency-add", actor_id, request, preview.preview_hash
    )
    added, replayed = store.execute(add), store.execute(add)
    assert (added.package_version, added.dependency_active, added.replayed) == (2, True, False)
    assert replayed.replayed and replayed.package_version == 2

    cycle_request = replace(
        request,
        package_id=request.predecessor_package_id,
        predecessor_package_id=request.package_id,
        expected_package_version=1,
        expected_predecessor_version=2,
    )
    with pytest.raises(WorkPackageDependencyConflict, match="acyclic"):
        store.preview(actor_id, cycle_request)

    remove_request = replace(
        request, operation=DependencyOperation.REMOVE, expected_package_version=2
    )
    remove_preview = store.preview(actor_id, remove_request)
    removed = store.execute(
        ChangeDependencyCommand(
            uuid4(), "dependency-remove", actor_id, remove_request, remove_preview.preview_hash
        )
    )
    assert (removed.package_version, removed.dependency_active) == (3, False)
    with engine.connect() as connection:
        counts = connection.execute(
            text(
                "SELECT "
                "(SELECT count(*) FROM work_package_history WHERE package_id=:package),"
                "(SELECT count(*) FROM work_package_dependency_commands),"
                "(SELECT count(*) FROM coeus_audit_events "
                " WHERE event_type LIKE 'work_package_dependency_%'),"
                "(SELECT count(*) FROM coeus_outbox "
                " WHERE event_type LIKE 'work_package_dependency_%')"
            ),
            {"package": request.package_id},
        ).one()
    assert tuple(counts) == (2, 2, 2, 2)
    with pytest.raises(DBAPIError), engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE work_package_dependency_commands SET result_package_version=99 "
                "WHERE command_id=:id"
            ),
            {"id": command_id},
        )
    engine.dispose()
