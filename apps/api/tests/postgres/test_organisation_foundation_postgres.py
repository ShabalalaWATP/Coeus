"""Real PostgreSQL constraints and shadow-repository tests."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import DBAPIError, IntegrityError

from coeus.core.config import Settings
from coeus.domain.organisation import (
    DeliveryRoute,
    EffectiveAuthorityEpoch,
    FindingSeverity,
    ManagementAction,
    MembershipRole,
    MembershipState,
    OrganisationCategory,
    OrganisationManagementGrant,
    OrganisationReconciliationCheckpoint,
    OrganisationReconciliationFinding,
    OrganisationTopologyRevision,
    OrganisationUnit,
    ReconciliationStatus,
    TeamCapabilityCoverage,
    TeamDeliveryProfile,
    TeamMembership,
)
from coeus.main import create_app
from coeus.persistence.organisation_postgres import PostgresOrganisationRepository

API_ROOT = Path(__file__).resolve().parents[2]
NOW = datetime(2026, 8, 3, 8, tzinfo=UTC)
pytestmark = pytest.mark.postgres


def _upgrade(database_url: str) -> None:
    config = Config(str(API_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "20260803_0017")


def _unit(unit_id: UUID, name: str, parent_id: UUID | None = None) -> OrganisationUnit:
    return OrganisationUnit(
        unit_id,
        name,
        name[:20],
        OrganisationCategory.DELIVERY_TEAM if parent_id else OrganisationCategory.COMMAND,
        parent_id,
        NOW,
    )


def _revision(unit: OrganisationUnit, path: tuple[UUID, ...]) -> OrganisationTopologyRevision:
    return OrganisationTopologyRevision(
        uuid4(), unit.unit_id, unit.parent_unit_id, path, NOW, uuid4(), uuid4()
    )


def _membership(
    user_id: UUID,
    unit_id: UUID,
    start: datetime,
    end: datetime | None,
    state: MembershipState,
) -> TeamMembership:
    return TeamMembership(
        uuid4(),
        user_id,
        unit_id,
        MembershipRole.MEMBER,
        state,
        state is MembershipState.ACTIVE,
        start,
        uuid4(),
        "Synthetic posting",
        "test",
        end,
    )


def test_tree_membership_constraints_and_repeated_upserts(postgres_database_url: str) -> None:
    _upgrade(postgres_database_url)
    engine = create_engine(postgres_database_url)
    repository = PostgresOrganisationRepository(engine)
    root = _unit(uuid4(), "Synthetic Command")
    child = _unit(uuid4(), "Synthetic RFA Team", root.unit_id)
    root_revision = _revision(root, (root.unit_id,))
    child_revision = _revision(child, (root.unit_id, child.unit_id))

    repository.upsert_unit(root, root_revision)
    repository.upsert_unit(root, root_revision)
    repository.upsert_unit(child, child_revision)
    repository.upsert_unit(child, child_revision)
    assert repository.get_unit(root.unit_id) == root
    assert repository.list_children(root.unit_id) == (child,)
    assert repository.list_descendants(root.unit_id) == (child,)
    assert repository.list_ancestors(child.unit_id) == (root,)

    user_id = uuid4()
    boundary = NOW + timedelta(days=10)
    historic = _membership(user_id, root.unit_id, NOW, boundary, MembershipState.ENDED)
    current = _membership(user_id, child.unit_id, boundary, None, MembershipState.ACTIVE)
    repository.upsert_membership(historic)
    repository.upsert_membership(historic)
    repository.upsert_membership(current)
    assert repository.effective_membership(user_id, boundary) == current

    overlap = _membership(
        user_id, root.unit_id, boundary + timedelta(days=1), None, MembershipState.ACTIVE
    )
    with pytest.raises(IntegrityError):
        repository.upsert_membership(overlap)
    cancelled = replace(
        overlap, membership_id=uuid4(), state=MembershipState.CANCELLED, assignment_eligible=False
    )
    repository.upsert_membership(cancelled)
    assert len(repository.list_memberships(user_id)) == 3

    with engine.begin() as connection, pytest.raises(DBAPIError):
        connection.execute(
            text(
                "INSERT INTO organisation_unit_closure"
                "(ancestor_unit_id, descendant_unit_id, depth) VALUES (:child, :root, 0)"
            ),
            {"child": child.unit_id, "root": root.unit_id},
        )
    with engine.begin() as connection, pytest.raises(DBAPIError, match="immutable"):
        connection.execute(text("UPDATE organisation_topology_revisions SET valid_from = now()"))
    engine.dispose()


def test_delivery_grants_epochs_and_reconciliation_are_idempotent(
    postgres_database_url: str,
) -> None:
    _upgrade(postgres_database_url)
    engine = create_engine(postgres_database_url)
    repository = PostgresOrganisationRepository(engine)
    unit = _unit(uuid4(), "Synthetic CM Team")
    repository.upsert_unit(unit, _revision(unit, (unit.unit_id,)))

    profile = TeamDeliveryProfile(uuid4(), unit.unit_id, DeliveryRoute.CM, 7, 37.5)
    repository.upsert_delivery_profile(profile)
    repository.upsert_delivery_profile(profile)
    coverage_one = TeamCapabilityCoverage(
        uuid4(), profile.profile_id, "synthetic-language", 3, NOW, uuid4()
    )
    coverage_two = TeamCapabilityCoverage(
        uuid4(), profile.profile_id, "synthetic-imagery", 4, NOW, uuid4()
    )
    for coverage in (coverage_one, coverage_two, coverage_one):
        repository.upsert_capability_coverage(coverage)

    manager_id = uuid4()
    grant = OrganisationManagementGrant(
        uuid4(),
        manager_id,
        unit.unit_id,
        ManagementAction.TASK_ASSIGN,
        True,
        NOW,
        uuid4(),
        "Synthetic manager grant",
    )
    repository.upsert_management_grant(grant)
    repository.upsert_management_grant(grant)
    assert repository.effective_grants(manager_id, NOW) == (grant,)
    revoked = replace(
        grant,
        grant_id=uuid4(),
        valid_from=NOW - timedelta(days=1),
        revoked_at=NOW,
        version=2,
    )
    repository.upsert_management_grant(revoked)
    assert repository.list_management_grants(root_unit_id=unit.unit_id) == (grant,)
    assert repository.list_management_grants(
        manager_user_id=manager_id, include_inactive=True
    ) == tuple(sorted((grant, revoked), key=lambda item: str(item.grant_id)))
    with pytest.raises(ValueError, match="limit"):
        repository.list_management_grants(limit=0)

    epoch = EffectiveAuthorityEpoch(manager_id, unit.unit_id, 2, NOW)
    repository.upsert_authority_epoch(epoch)
    repository.upsert_authority_epoch(replace(epoch, epoch=1, advanced_at=NOW - timedelta(days=1)))
    checkpoint = OrganisationReconciliationCheckpoint(
        uuid4(), "synthetic-teams", "a" * 64, ReconciliationStatus.RUNNING, NOW, {"offset": 0}
    )
    repository.upsert_checkpoint(checkpoint)
    repository.upsert_checkpoint(replace(checkpoint, cursor={"offset": 10}))
    finding = OrganisationReconciliationFinding(
        uuid4(),
        checkpoint.checkpoint_id,
        "overlapping-membership",
        FindingSeverity.BLOCKING,
        "synthetic-user",
        {"count": 2},
        NOW,
    )
    repository.upsert_finding(finding)
    repository.upsert_finding(replace(finding, disposition="Awaiting review"))

    with engine.connect() as connection:
        assert (
            connection.execute(
                text("SELECT route FROM team_delivery_profiles WHERE profile_id = :profile_id"),
                {"profile_id": profile.profile_id},
            ).scalar_one()
            == "cm"
        )
        assert (
            connection.execute(text("SELECT count(*) FROM team_capability_coverage")).scalar_one()
            == 2
        )
        assert (
            connection.execute(text("SELECT epoch FROM effective_authority_epochs")).scalar_one()
            == 2
        )
        assert (
            connection.execute(
                text("SELECT cursor ->> 'offset' FROM organisation_reconciliation_checkpoints")
            ).scalar_one()
            == "10"
        )
        assert inspect(engine).get_unique_constraints("team_delivery_profiles")
    engine.dispose()


def test_alembic_schema_contains_all_foundation_tables(postgres_database_url: str) -> None:
    _upgrade(postgres_database_url)
    engine = create_engine(postgres_database_url)
    tables = set(inspect(engine).get_table_names())
    assert {
        "organisation_units",
        "organisation_unit_closure",
        "organisation_topology_revisions",
        "team_delivery_profiles",
        "team_capability_coverage",
        "team_memberships",
        "team_management_grants",
        "effective_authority_epochs",
        "organisation_reconciliation_checkpoints",
        "organisation_reconciliation_findings",
    } <= tables
    with engine.connect() as connection:
        assert (
            connection.execute(
                text("SELECT 1 FROM pg_extension WHERE extname = 'btree_gist'")
            ).scalar_one()
            == 1
        )
    engine.dispose()


def test_explicit_shadow_mode_reconciles_during_application_startup(
    postgres_database_url: str,
) -> None:
    _upgrade(postgres_database_url)
    app = create_app(
        Settings(
            environment="test",
            persistence_provider="postgres",
            database_url=postgres_database_url,
            organisation_mode="shadow",
        )
    )
    result = app.state.organisation_reconciliation_result
    repository = app.state.organisation_repository
    assert result.units_written == len(app.state.team_repository.list_teams())
    assert result.memberships_written > 0
    assert repository.list_roots()
    app.state.organisation_engine.dispose()
