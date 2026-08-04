"""Changed-source convergence tests for the organisation shadow."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

from coeus.domain.auth import RoleName, UserAccount
from coeus.domain.teams import OrgTeam, TeamKind
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
    command.upgrade(config, "20260803_0018")


def test_changed_team_metadata_capability_and_account_state_converge(
    postgres_database_url: str,
) -> None:
    _upgrade(postgres_database_url)
    engine = create_engine(postgres_database_url)
    service = OrganisationReconciliationService(PostgresOrganisationReconciliation(engine))
    analyst = UserAccount(
        uuid4(),
        "analyst@example.test",
        "Synthetic Analyst",
        frozenset({RoleName.INTELLIGENCE_ANALYST}),
        frozenset(),
        "hash",
        True,
        1,
    )
    original = OrgTeam(
        uuid4(),
        "Original RFA Team",
        TeamKind.RFA,
        member_user_ids=(analyst.user_id,),
        capability_team_id="RFA-ORIGINAL",
        created_at=NOW,
    )
    actor_id = uuid4()
    service.reconcile(teams=(original,), users=(analyst,), actor_user_id=actor_id, effective_at=NOW)
    changed = replace(
        original,
        name="Renamed RFA Team",
        capability_team_id="RFA-REVISED",
        is_active=False,
    )
    service.reconcile(
        teams=(changed,),
        users=(analyst,),
        actor_user_id=actor_id,
        effective_at=NOW + timedelta(hours=1),
    )
    reactivated = replace(changed, is_active=True)
    service.reconcile(
        teams=(reactivated,),
        users=(analyst,),
        actor_user_id=uuid4(),
        effective_at=NOW + timedelta(hours=2),
    )

    with engine.connect() as connection:
        unit = connection.execute(
            text("SELECT name, is_active, version FROM organisation_units")
        ).one()
        profile = connection.execute(
            text("SELECT is_active, policy_version FROM team_delivery_profiles")
        ).one()
        membership = connection.execute(
            text("SELECT state, assignment_eligible, version FROM team_memberships")
        ).one()
        coverage = connection.execute(
            text(
                "SELECT capability_id, valid_until FROM team_capability_coverage "
                "ORDER BY capability_id"
            )
        ).all()
        assert unit == ("Renamed RFA Team", True, 3)
        assert profile == (True, 3)
        assert membership == ("active", True, 3)
        assert coverage[0][0] == "RFA-ORIGINAL"
        assert coverage[0][1] == NOW + timedelta(hours=1)
        assert coverage[1][0] == "RFA-REVISED"
        assert coverage[1][1] is None
        assert connection.execute(text("SELECT count(*) FROM coeus_audit_events")).scalar_one() == 3
    engine.dispose()


def test_person_can_rejoin_after_a_completed_legacy_posting(
    postgres_database_url: str,
) -> None:
    _upgrade(postgres_database_url)
    engine = create_engine(postgres_database_url)
    service = OrganisationReconciliationService(PostgresOrganisationReconciliation(engine))
    analyst = UserAccount(
        uuid4(),
        "analyst@example.test",
        "Synthetic Analyst",
        frozenset({RoleName.INTELLIGENCE_ANALYST}),
        frozenset(),
        "hash",
        True,
        1,
    )
    assigned = OrgTeam(
        uuid4(),
        "Synthetic CM Team",
        TeamKind.CM,
        member_user_ids=(analyst.user_id,),
        created_at=NOW,
    )
    unassigned = replace(assigned, member_user_ids=())
    actor_id = uuid4()
    service.reconcile(teams=(assigned,), users=(analyst,), actor_user_id=actor_id, effective_at=NOW)
    service.reconcile(
        teams=(unassigned,),
        users=(analyst,),
        actor_user_id=actor_id,
        effective_at=NOW + timedelta(hours=1),
    )
    service.reconcile(
        teams=(assigned,),
        users=(analyst,),
        actor_user_id=actor_id,
        effective_at=NOW + timedelta(hours=2),
    )

    with engine.connect() as connection:
        postings = connection.execute(
            text("SELECT state, valid_from, valid_until FROM team_memberships ORDER BY valid_from")
        ).all()
        assert postings == [
            ("ended", NOW, NOW + timedelta(hours=1)),
            ("active", NOW + timedelta(hours=2), None),
        ]
    engine.dispose()


def test_same_timestamp_a_b_a_metadata_transitions_each_emit_evidence(
    postgres_database_url: str,
) -> None:
    _upgrade(postgres_database_url)
    engine = create_engine(postgres_database_url)
    service = OrganisationReconciliationService(PostgresOrganisationReconciliation(engine))
    team_a = OrgTeam(uuid4(), "Team A", TeamKind.JIOC, created_at=NOW)
    team_b = replace(team_a, name="Team B")
    actor_id = uuid4()
    for team in (team_a, team_b, team_a):
        service.reconcile(teams=(team,), users=(), actor_user_id=actor_id, effective_at=NOW)

    with engine.connect() as connection:
        assert (
            connection.execute(text("SELECT name FROM organisation_units")).scalar_one() == "Team A"
        )
        assert connection.execute(text("SELECT count(*) FROM coeus_audit_events")).scalar_one() == 3
        assert connection.execute(text("SELECT count(*) FROM coeus_outbox")).scalar_one() == 3
    engine.dispose()


def test_removed_source_team_is_retired_without_touching_manual_units(
    postgres_database_url: str,
) -> None:
    _upgrade(postgres_database_url)
    engine = create_engine(postgres_database_url)
    service = OrganisationReconciliationService(PostgresOrganisationReconciliation(engine))
    retained = OrgTeam(uuid4(), "Retained Team", TeamKind.RFA, created_at=NOW)
    removed = OrgTeam(
        uuid4(),
        "Removed Team",
        TeamKind.CM,
        capability_team_id="REMOVED-CAPABILITY",
        created_at=NOW,
    )
    actor_id = uuid4()
    service.reconcile(teams=(retained, removed), users=(), actor_user_id=actor_id, effective_at=NOW)
    manual_unit_id = uuid4()
    manual_profile_id = uuid4()
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO organisation_units"
                "(unit_id,name,short_name,category,parent_unit_id,is_active,valid_from,"
                "valid_until,time_zone,description,version,provenance) VALUES "
                "(:unit_id,'Manual Team','Manual','delivery_team',NULL,true,:now,NULL,"
                "'Europe/London','Manual hierarchy unit',1,'manual')"
            ),
            {"unit_id": manual_unit_id, "now": NOW},
        )
        connection.execute(
            text(
                "INSERT INTO team_delivery_profiles"
                "(profile_id,unit_id,route,wip_limit,weekly_hours,policy_version,is_active,"
                "provenance) VALUES (:profile_id,:unit_id,'rfa',5,37,1,true,'manual')"
            ),
            {"profile_id": manual_profile_id, "unit_id": manual_unit_id},
        )
        connection.execute(
            text(
                "INSERT INTO organisation_unit_closure"
                "(ancestor_unit_id,descendant_unit_id,depth) VALUES (:unit_id,:unit_id,0)"
            ),
            {"unit_id": manual_unit_id},
        )

    service.reconcile(
        teams=(retained,),
        users=(),
        actor_user_id=actor_id,
        effective_at=NOW + timedelta(hours=1),
    )

    with engine.connect() as connection:
        removed_state = connection.execute(
            text(
                "SELECT unit.is_active, profile.is_active, coverage.valid_until "
                "FROM organisation_units unit "
                "JOIN team_delivery_profiles profile ON profile.unit_id=unit.unit_id "
                "JOIN team_capability_coverage coverage "
                "ON coverage.profile_id=profile.profile_id WHERE unit.unit_id=:unit_id"
            ),
            {"unit_id": removed.team_id},
        ).one()
        manual_state = connection.execute(
            text(
                "SELECT unit.is_active, profile.is_active FROM organisation_units unit "
                "JOIN team_delivery_profiles profile ON profile.unit_id=unit.unit_id "
                "WHERE unit.unit_id=:unit_id"
            ),
            {"unit_id": manual_unit_id},
        ).one()
        assert removed_state == (False, False, NOW + timedelta(hours=1))
        assert manual_state == (True, True)
    engine.dispose()
