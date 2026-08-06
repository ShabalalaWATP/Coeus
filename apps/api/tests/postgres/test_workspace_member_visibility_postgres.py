"""Real PostgreSQL proof for the roster a posting alone may read.

Being posted to a team is enough to see who else is in it. It is not management
authority, so it must not reach child teams, another unit, or any other read.
"""

from pathlib import Path
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from organisation_account_support import activate_principals
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from workspace_operations_support import seed_delivery_profile, seed_membership

from coeus.domain.organisation_bootstrap import OrganisationBootstrapPlan
from coeus.domain.workspace_operations import WorkspaceOperationsDenied, WorkspaceScope
from coeus.persistence.organisation_bootstrap_postgres import PostgresOrganisationBootstrapStore
from coeus.persistence.workspace_operations_postgres import PostgresWorkspaceOperationsStore

API_ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.postgres


def _bootstrap(database_url: str) -> tuple[Engine, UUID, UUID]:
    """A unit holding two ordinary members and no management grant at all."""
    config = Config(str(API_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "head")
    engine = create_engine(database_url)
    member, colleague, root_id = uuid4(), uuid4(), uuid4()
    PostgresOrganisationBootstrapStore(engine).bootstrap(
        OrganisationBootstrapPlan(
            uuid4(), uuid4(), root_id, "Synthetic Team", "SYN", "Europe/London", ""
        )
    )
    activate_principals(engine, member, colleague)
    seed_delivery_profile(engine, root_id, ("regional-analysis",))
    seed_membership(engine, member, root_id)
    seed_membership(engine, colleague, root_id)
    return engine, member, root_id


def test_a_posting_reads_the_members_own_roster(postgres_database_url: str) -> None:
    engine, member, root_id = _bootstrap(postgres_database_url)

    roster = PostgresWorkspaceOperationsStore(engine).people(member, root_id, WorkspaceScope.DIRECT)

    assert member in {item.user_id for item in roster}
    assert len(roster) == 2
    engine.dispose()


def test_a_posting_opens_no_other_unit_scope_or_read(postgres_database_url: str) -> None:
    engine, member, root_id = _bootstrap(postgres_database_url)
    store = PostgresWorkspaceOperationsStore(engine)

    for call in (
        lambda: store.people(member, root_id, WorkspaceScope.DESCENDANTS),
        lambda: store.people(member, uuid4(), WorkspaceScope.DIRECT),
        lambda: store.overview(member, root_id, WorkspaceScope.DIRECT),
        lambda: store.capabilities(member, root_id, WorkspaceScope.DIRECT),
        lambda: store.policy(member, root_id),
        lambda: store.analytics(member, root_id, WorkspaceScope.DIRECT),
        lambda: store.search(member, root_id, WorkspaceScope.DIRECT, "Synthetic", 20),
    ):
        with pytest.raises(WorkspaceOperationsDenied):
            call()
    engine.dispose()


def test_a_suspended_member_keeps_no_roster_read(postgres_database_url: str) -> None:
    engine, member, root_id = _bootstrap(postgres_database_url)
    with engine.begin() as connection:
        connection.execute(
            text("UPDATE identity_account_projection SET is_active=false WHERE user_id=:actor"),
            {"actor": member},
        )

    with pytest.raises(WorkspaceOperationsDenied):
        PostgresWorkspaceOperationsStore(engine).people(member, root_id, WorkspaceScope.DIRECT)
    engine.dispose()
