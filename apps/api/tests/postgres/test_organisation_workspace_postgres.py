"""Real PostgreSQL evidence for scoped organisation workspace discovery."""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from organisation_account_support import activate_principals
from sqlalchemy import create_engine

from coeus.domain.organisation import (
    ManagementAction,
    MembershipRole,
    MembershipState,
    OrganisationCategory,
    OrganisationManagementGrant,
    OrganisationTopologyRevision,
    OrganisationUnit,
    TeamMembership,
)
from coeus.domain.organisation_workspace import WorkspaceRelationship
from coeus.persistence.organisation_postgres import PostgresOrganisationRepository
from coeus.persistence.organisation_workspace_postgres import PostgresOrganisationWorkspaceStore

API_ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.postgres


def _upgrade(database_url: str) -> None:
    config = Config(str(API_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "head")


def _unit(name: str, now: datetime, parent: OrganisationUnit | None = None) -> OrganisationUnit:
    return OrganisationUnit(
        uuid4(),
        name,
        name[:16],
        OrganisationCategory.DELIVERY_TEAM if parent else OrganisationCategory.COMMAND,
        None if parent is None else parent.unit_id,
        now - timedelta(days=1),
    )


def _add_unit(repository, unit, actor_id, path):  # type: ignore[no-untyped-def]
    repository.upsert_unit(
        unit,
        OrganisationTopologyRevision(
            uuid4(), unit.unit_id, unit.parent_unit_id, path, unit.valid_from, uuid4(), actor_id
        ),
    )


def _grant(actor_id, unit_id, action, descendants=False):  # type: ignore[no-untyped-def]
    return OrganisationManagementGrant(
        uuid4(),
        actor_id,
        unit_id,
        action,
        descendants,
        datetime.now(UTC) - timedelta(days=1),
        actor_id,
        "Synthetic workspace authority.",
    )


def test_home_and_managed_workspaces_require_independent_scoped_actions(
    postgres_database_url: str,
) -> None:
    _upgrade(postgres_database_url)
    engine = create_engine(postgres_database_url)
    repository = PostgresOrganisationRepository(engine)
    now, actor_id = datetime.now(UTC), uuid4()
    activate_principals(engine, actor_id)
    root = _unit("Synthetic Command", now)
    home = _unit("Synthetic Home Team", now, root)
    direct = _unit("Synthetic Direct Scope", now)
    hidden = _unit("Synthetic Hidden Command", now)
    _add_unit(repository, root, actor_id, (root.unit_id,))
    _add_unit(repository, home, actor_id, (root.unit_id, home.unit_id))
    _add_unit(repository, direct, actor_id, (direct.unit_id,))
    _add_unit(repository, hidden, actor_id, (hidden.unit_id,))
    repository.upsert_membership(
        TeamMembership(
            uuid4(),
            actor_id,
            home.unit_id,
            MembershipRole.MANAGER,
            MembershipState.ACTIVE,
            True,
            now - timedelta(days=1),
            actor_id,
            "Synthetic single-home posting.",
            "test",
        )
    )
    for grant in (
        _grant(actor_id, root.unit_id, ManagementAction.WORKSPACE_VIEW),
        _grant(actor_id, root.unit_id, ManagementAction.WORKSPACE_VIEW, True),
        _grant(actor_id, root.unit_id, ManagementAction.ORGANISATION_VIEW, True),
        _grant(actor_id, root.unit_id, ManagementAction.CALENDAR_VIEW_AVAILABILITY, True),
        _grant(actor_id, root.unit_id, ManagementAction.TASK_VIEW, True),
        _grant(actor_id, home.unit_id, ManagementAction.WORKSPACE_VIEW, False),
        _grant(actor_id, home.unit_id, ManagementAction.ORGANISATION_VIEW, False),
        _grant(actor_id, direct.unit_id, ManagementAction.WORKSPACE_VIEW, True),
        _grant(actor_id, direct.unit_id, ManagementAction.ORGANISATION_VIEW, False),
        _grant(actor_id, hidden.unit_id, ManagementAction.WORKSPACE_VIEW, True),
        _grant(actor_id, hidden.unit_id, ManagementAction.CALENDAR_VIEW_DETAIL, True),
    ):
        repository.upsert_management_grant(grant)

    page = PostgresOrganisationWorkspaceStore(engine).list_actor_workspaces(actor_id)

    assert not page.truncated
    assert page.workspaces[0].unit.unit_id == home.unit_id
    assert page.workspaces[0].relationship is WorkspaceRelationship.HOME
    by_id = {item.unit.unit_id: item for item in page.workspaces}
    assert set(by_id) == {home.unit_id, root.unit_id, direct.unit_id}
    home_workspace, managed_workspace = page.workspaces[0], by_id[root.unit_id]
    assert home_workspace.can_view_availability and not home_workspace.can_view_detail
    assert managed_workspace.include_descendants
    assert managed_workspace.can_view_availability and not managed_workspace.can_view_detail
    assert managed_workspace.can_view_tasks
    assert home_workspace.can_view_tasks
    assert not by_id[direct.unit_id].include_descendants

    empty_page = PostgresOrganisationWorkspaceStore(engine).list_actor_workspaces(uuid4())
    assert empty_page.workspaces == () and not empty_page.truncated
    engine.dispose()
