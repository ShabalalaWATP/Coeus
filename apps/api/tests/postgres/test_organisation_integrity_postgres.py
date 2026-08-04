"""Adversarial organisation authority and reconciliation tests."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError, IntegrityError

from coeus.domain.auth import RoleName, UserAccount
from coeus.domain.organisation import (
    ManagementAction,
    MembershipRole,
    MembershipState,
    OrganisationCategory,
    OrganisationManagementGrant,
    OrganisationReconciliationCheckpoint,
    OrganisationTopologyRevision,
    OrganisationUnit,
    ReconciliationStatus,
    TeamMembership,
)
from coeus.domain.organisation_reconciliation import OrganisationReconciliationPlan
from coeus.domain.teams import OrgTeam, TeamKind
from coeus.persistence.organisation_postgres import PostgresOrganisationRepository
from coeus.persistence.organisation_reconciliation_postgres import (
    PostgresOrganisationReconciliation,
)
from coeus.services.organisation_reconciliation import OrganisationReconciliationService

API_ROOT = Path(__file__).resolve().parents[2]
NOW = datetime(2026, 8, 3, 8, tzinfo=UTC)
pytestmark = pytest.mark.postgres


def _upgrade(database_url: str) -> None:
    config = Config(str(API_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "20260803_0017")


def _unit(name: str = "Synthetic Command", *, version: int = 1) -> OrganisationUnit:
    return OrganisationUnit(
        uuid4(), name, name[:20], OrganisationCategory.COMMAND, None, NOW, version=version
    )


def _revision(
    unit: OrganisationUnit, *, revision_id: UUID | None = None
) -> OrganisationTopologyRevision:
    return OrganisationTopologyRevision(
        revision_id or uuid4(), unit.unit_id, None, (unit.unit_id,), NOW, uuid4(), uuid4()
    )


def test_stale_authority_and_revision_replays_fail_closed(postgres_database_url: str) -> None:
    _upgrade(postgres_database_url)
    engine = create_engine(postgres_database_url)
    repository = PostgresOrganisationRepository(engine)
    unit = _unit()
    revision = _revision(unit)
    repository.upsert_unit(unit, revision)
    current_unit = replace(unit, name="Current Command", short_name="Current", version=2)
    repository.upsert_unit(current_unit, revision)
    with pytest.raises(ValueError, match="unit identity"):
        repository.upsert_unit(unit, revision)
    assert repository.get_unit(unit.unit_id) == current_unit

    user_id = uuid4()
    membership = TeamMembership(
        uuid4(),
        user_id,
        unit.unit_id,
        MembershipRole.MEMBER,
        MembershipState.ACTIVE,
        True,
        NOW,
        uuid4(),
        "Synthetic posting",
        "test",
    )
    ended = replace(
        membership,
        state=MembershipState.ENDED,
        assignment_eligible=False,
        valid_until=NOW + timedelta(days=1),
        version=2,
    )
    repository.upsert_membership(membership)
    repository.upsert_membership(ended)
    with pytest.raises(ValueError, match="membership identity"):
        repository.upsert_membership(membership)

    grant = OrganisationManagementGrant(
        uuid4(),
        user_id,
        unit.unit_id,
        ManagementAction.TASK_ASSIGN,
        False,
        NOW,
        uuid4(),
        "Synthetic grant",
    )
    revoked = replace(
        grant,
        valid_until=NOW + timedelta(days=2),
        revoked_at=NOW + timedelta(days=1),
        version=2,
    )
    repository.upsert_management_grant(grant)
    repository.upsert_management_grant(revoked)
    with pytest.raises(ValueError, match="management grant identity"):
        repository.upsert_management_grant(grant)

    conflicting = replace(revision, change_command_id=uuid4())
    with pytest.raises(ValueError, match="revision identity"):
        repository.upsert_unit(current_unit, conflicting)
    engine.dispose()


def test_database_rejects_incomplete_closure_and_parent_cycles(postgres_database_url: str) -> None:
    _upgrade(postgres_database_url)
    engine = create_engine(postgres_database_url)
    repository = PostgresOrganisationRepository(engine)
    root = _unit()
    child = OrganisationUnit(
        uuid4(),
        "Synthetic Child",
        "Child",
        OrganisationCategory.DELIVERY_TEAM,
        root.unit_id,
        NOW,
    )
    repository.upsert_unit(root, _revision(root))
    repository.upsert_unit(
        child,
        OrganisationTopologyRevision(
            uuid4(),
            child.unit_id,
            root.unit_id,
            (root.unit_id, child.unit_id),
            NOW,
            uuid4(),
            uuid4(),
        ),
    )
    with pytest.raises(DBAPIError, match="immutable"), engine.begin() as connection:
        connection.execute(
            text(
                "DELETE FROM organisation_unit_closure "
                "WHERE ancestor_unit_id = :root AND descendant_unit_id = :child"
            ),
            {"root": root.unit_id, "child": child.unit_id},
        )
    with pytest.raises(DBAPIError, match=r"cycle|inconsistent"), engine.begin() as connection:
        connection.execute(
            text("UPDATE organisation_units SET parent_unit_id = :child WHERE unit_id = :root"),
            {"root": root.unit_id, "child": child.unit_id},
        )
    orphan_id = uuid4()
    with pytest.raises(DBAPIError, match="closure"), engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO organisation_units"
                "(unit_id,name,short_name,category,parent_unit_id,is_active,valid_from,"
                "time_zone,description,version) VALUES "
                "(:id,'Orphan','Orphan','command',NULL,true,:now,'Europe/London','',1)"
            ),
            {"id": orphan_id, "now": NOW},
        )
    engine.dispose()


def test_reconciliation_is_atomic_ends_absent_people_and_emits_evidence(
    postgres_database_url: str,
) -> None:
    _upgrade(postgres_database_url)
    engine = create_engine(postgres_database_url)
    committer = PostgresOrganisationReconciliation(engine)
    service = OrganisationReconciliationService(committer)
    analyst = UserAccount(
        uuid4(),
        "analyst@example.test",
        "Analyst",
        frozenset({RoleName.INTELLIGENCE_ANALYST}),
        frozenset(),
        "hash",
        True,
        1,
    )
    team = OrgTeam(
        uuid4(),
        "Synthetic RFA Team",
        TeamKind.RFA,
        member_user_ids=(analyst.user_id,),
        created_at=NOW,
    )
    actor_id = uuid4()
    service.reconcile(teams=(team,), users=(analyst,), actor_user_id=actor_id, effective_at=NOW)
    later = NOW + timedelta(days=2)
    service.reconcile(
        teams=(replace(team, member_user_ids=()),),
        users=(analyst,),
        actor_user_id=actor_id,
        effective_at=later,
    )
    service.reconcile(
        teams=(replace(team, member_user_ids=()),),
        users=(analyst,),
        actor_user_id=actor_id,
        effective_at=later + timedelta(hours=1),
    )
    with engine.connect() as connection:
        assert (
            connection.execute(text("SELECT state FROM team_memberships")).scalar_one() == "ended"
        )
        assert connection.execute(text("SELECT count(*) FROM coeus_audit_events")).scalar_one() == 2
        assert connection.execute(text("SELECT count(*) FROM coeus_outbox")).scalar_one() == 2
        assert (
            connection.execute(text("SELECT epoch FROM effective_authority_epochs")).scalar_one()
            == 2
        )

    invalid_checkpoint = OrganisationReconciliationCheckpoint(
        uuid4(),
        "legacy-flat-teams-v1",
        "f" * 64,
        ReconciliationStatus.COMPLETED,
        later,
        {},
        later,
    )
    invalid_membership = TeamMembership(
        uuid4(),
        analyst.user_id,
        uuid4(),
        MembershipRole.MEMBER,
        MembershipState.ACTIVE,
        True,
        later,
        actor_id,
        "Invalid target",
        "legacy-flat-teams-v1",
    )
    invalid_plan = OrganisationReconciliationPlan(
        invalid_checkpoint, actor_id, later, (), (), (), (invalid_membership,), ()
    )
    with pytest.raises(IntegrityError):
        committer.apply_reconciliation(invalid_plan)
    with engine.connect() as connection:
        assert (
            connection.execute(
                text(
                    "SELECT count(*) FROM organisation_reconciliation_checkpoints "
                    "WHERE checkpoint_id = :checkpoint_id"
                ),
                {"checkpoint_id": invalid_checkpoint.checkpoint_id},
            ).scalar_one()
            == 0
        )
    engine.dispose()


def test_reconciliation_reapplies_a_historical_digest_as_the_latest_snapshot(
    postgres_database_url: str,
) -> None:
    _upgrade(postgres_database_url)
    engine = create_engine(postgres_database_url)
    service = OrganisationReconciliationService(PostgresOrganisationReconciliation(engine))
    first = UserAccount(
        uuid4(),
        "first@example.test",
        "First Analyst",
        frozenset({RoleName.INTELLIGENCE_ANALYST}),
        frozenset(),
        "hash",
        True,
        1,
    )
    second = replace(first, user_id=uuid4(), username="second@example.test", display_name="Second")
    team_a = OrgTeam(
        uuid4(),
        "Synthetic RFA Team",
        TeamKind.RFA,
        member_user_ids=(first.user_id,),
        capability_team_id="RFA-SYNTHETIC",
        created_at=NOW,
    )
    team_b = replace(team_a, member_user_ids=(first.user_id, second.user_id))
    actor_id = uuid4()
    service.reconcile(
        teams=(team_a,), users=(first, second), actor_user_id=actor_id, effective_at=NOW
    )
    service.reconcile(
        teams=(team_b,),
        users=(first, second),
        actor_user_id=actor_id,
        effective_at=NOW + timedelta(hours=1),
    )
    service.reconcile(
        teams=(team_a,),
        users=(first, second),
        actor_user_id=actor_id,
        effective_at=NOW + timedelta(hours=2),
    )

    with engine.connect() as connection:
        states = dict(connection.execute(text("SELECT user_id, state FROM team_memberships")).all())
        assert states[first.user_id] == "active"
        assert states[second.user_id] == "ended"
        assert connection.execute(text("SELECT count(*) FROM coeus_audit_events")).scalar_one() == 3
        assert connection.execute(text("SELECT count(*) FROM coeus_outbox")).scalar_one() == 3
    engine.dispose()
