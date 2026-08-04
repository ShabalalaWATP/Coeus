"""Real PostgreSQL evidence for reviewed contributor lifecycle commands."""

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
from coeus.domain.my_work import MyWorkColumn
from coeus.domain.organisation_bootstrap import OrganisationBootstrapPlan
from coeus.domain.tickets import IntakeDetails, TicketRecord
from coeus.domain.work_package_contributors import (
    ChangeContributorCommand,
    ContributorChangeRequest,
    ContributorOperation,
)
from coeus.persistence.my_work_postgres import PostgresMyWorkStore
from coeus.persistence.organisation_bootstrap_postgres import PostgresOrganisationBootstrapStore
from coeus.persistence.state_store import PostgresStateStore
from coeus.persistence.work_package_contributors_postgres import (
    PostgresWorkPackageContributorStore,
)
from coeus.repositories.tickets import InMemoryTicketRepository

API_ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.postgres


def _upgrade(database_url: str) -> None:
    # Contributor reservations carry the participant role added after 0033, so
    # the whole schema is required rather than the contributor revision alone.
    config = Config(str(API_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "head")


def _insert_command_evidence(
    database_url: str,
) -> tuple[UUID, ContributorChangeRequest]:
    engine = create_engine(database_url)
    actor_id, contributor_id, owner_id, unit_id = uuid4(), uuid4(), uuid4(), uuid4()
    topology = PostgresOrganisationBootstrapStore(engine).bootstrap(
        OrganisationBootstrapPlan(
            uuid4(), actor_id, unit_id, "Synthetic RFA Team", "SYN-RFA", "Europe/London", ""
        )
    )
    ticket = TicketRecord(
        uuid4(),
        "TCK-CONTRIB-0001",
        uuid4(),
        TicketState.ANALYST_IN_PROGRESS,
        IntakeDetails(title="Synthetic contributor task"),
    )
    InMemoryTicketRepository(PostgresStateStore(database_url, "relational")).save(ticket)
    package_id, membership_id, grant_id = uuid4(), uuid4(), uuid4()
    now = datetime.now(UTC)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO identity_account_projection"
                "(user_id,is_active,roles,credential_version,source_hash) VALUES "
                "(:actor,true,ARRAY['Administrator'],2,:actor_hash),"
                "(:contributor,true,ARRAY['Analyst'],7,:contributor_hash)"
            ),
            {
                "actor": actor_id,
                "actor_hash": "a" * 64,
                "contributor": contributor_id,
                "contributor_hash": "b" * 64,
            },
        )
        connection.execute(
            text(
                "INSERT INTO team_memberships"
                "(membership_id,user_id,unit_id,role,state,assignment_eligible,valid_from,"
                "created_by_user_id,reason,provenance,version) VALUES "
                "(:membership,:contributor,:unit,'member','active',true,:now,:actor,"
                "'Synthetic home posting','test',3)"
            ),
            {
                "membership": membership_id,
                "contributor": contributor_id,
                "unit": unit_id,
                "actor": actor_id,
                "now": now,
            },
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
                "(:package,:ticket,'rfa',:unit,:owner,'Synthetic contribution','ready',0,1,"
                "'test',:now,:now)"
            ),
            {
                "package": package_id,
                "ticket": ticket.ticket_id,
                "unit": unit_id,
                "owner": owner_id,
                "now": now,
            },
        )
    engine.dispose()
    return actor_id, ContributorChangeRequest(
        unit_id,
        package_id,
        contributor_id,
        ContributorOperation.ADD,
        1,
        2,
        grant_id,
        4,
        membership_id,
        3,
        7,
        "b" * 64,
    )


def test_add_replay_and_end_contributor_updates_my_work_atomically(
    postgres_database_url: str,
) -> None:
    _upgrade(postgres_database_url)
    actor_id, request = _insert_command_evidence(postgres_database_url)
    engine = create_engine(postgres_database_url)
    store = PostgresWorkPackageContributorStore(engine)
    preview = store.preview(actor_id, request)
    add = ChangeContributorCommand(
        uuid4(), "contributor-add", actor_id, request, preview.preview_hash
    )

    added = store.execute(add)
    replayed = store.execute(add)
    personal = PostgresMyWorkStore(engine).list_my_work(
        request.contributor_user_id,
        include_completed=False,
        column=MyWorkColumn.READY,
        cursor=None,
        limit=10,
    )
    assert added.package_version == 2 and added.contributor_active
    assert replayed.replayed and replayed.package_version == 2
    assert [card.package_id for card in personal.cards] == [request.package_id]

    end_request = replace(request, operation=ContributorOperation.END, expected_package_version=2)
    end_preview = store.preview(actor_id, end_request)
    ended = store.execute(
        ChangeContributorCommand(
            uuid4(), "contributor-end", actor_id, end_request, end_preview.preview_hash
        )
    )
    personal = PostgresMyWorkStore(engine).list_my_work(
        request.contributor_user_id,
        include_completed=False,
        column=None,
        cursor=None,
        limit=10,
    )
    assert ended.package_version == 3 and not ended.contributor_active
    assert personal.cards == ()
    with engine.connect() as connection:
        counts = connection.execute(
            text(
                "SELECT "
                "(SELECT count(*) FROM work_package_history WHERE package_id=:package),"
                "(SELECT count(*) FROM work_package_contributor_commands "
                " WHERE package_id=:package),"
                "(SELECT count(*) FROM coeus_audit_events "
                " WHERE event_type LIKE 'work_package_contributor_%'),"
                "(SELECT count(*) FROM coeus_outbox "
                " WHERE event_type LIKE 'work_package_contributor_%')"
            ),
            {"package": request.package_id},
        ).one()
    assert tuple(counts) == (2, 2, 2, 2)
    engine.dispose()


def test_contributor_command_history_is_immutable(postgres_database_url: str) -> None:
    _upgrade(postgres_database_url)
    actor_id, request = _insert_command_evidence(postgres_database_url)
    engine = create_engine(postgres_database_url)
    store = PostgresWorkPackageContributorStore(engine)
    preview = store.preview(actor_id, request)
    command_id = uuid4()
    store.execute(
        ChangeContributorCommand(
            command_id, "contributor-immutable", actor_id, request, preview.preview_hash
        )
    )
    with pytest.raises(DBAPIError), engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE work_package_contributor_commands "
                "SET result_package_version=99 WHERE command_id=:command_id"
            ),
            {"command_id": command_id},
        )
    engine.dispose()
