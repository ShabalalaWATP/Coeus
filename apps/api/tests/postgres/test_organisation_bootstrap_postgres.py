"""Real PostgreSQL evidence for the one-shot organisation bootstrap."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

from coeus.domain.organisation import ManagementAction
from coeus.domain.organisation_bootstrap import (
    OrganisationBootstrapPlan,
    OrganisationBootstrapUnavailable,
)
from coeus.persistence.organisation_bootstrap_postgres import (
    PostgresOrganisationBootstrapStore,
)

API_ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.postgres


def _upgrade(database_url: str) -> None:
    config = Config(str(API_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "20260803_0020")


def _plan() -> OrganisationBootstrapPlan:
    return OrganisationBootstrapPlan(
        uuid4(),
        uuid4(),
        uuid4(),
        "Synthetic Defence Intelligence",
        "Synthetic DI",
        "Europe/London",
        "Synthetic exercise root.",
    )


def test_bootstrap_creates_root_explicit_ceilings_and_permanent_marker(
    postgres_database_url: str,
) -> None:
    _upgrade(postgres_database_url)
    engine = create_engine(postgres_database_url)
    store = PostgresOrganisationBootstrapStore(engine)
    plan = _plan()
    result = store.bootstrap(plan)
    assert result.root_unit_id == plan.root_unit_id
    assert len(result.grant_ids) == len(ManagementAction)

    with engine.connect() as connection:
        root = connection.execute(
            text("SELECT name,provenance,version FROM organisation_units")
        ).one()
        closure = connection.execute(
            text("SELECT ancestor_unit_id,descendant_unit_id,depth FROM organisation_unit_closure")
        ).one()
        actions = set(
            connection.execute(text("SELECT action FROM team_management_grants")).scalars()
        )
        marker = connection.execute(
            text("SELECT ceremony_id,root_unit_id FROM organisation_bootstrap_state")
        ).one()
        evidence = dict(
            connection.execute(
                text("SELECT event_type,count(*) FROM coeus_audit_events GROUP BY event_type")
            ).all()
        )
        outbox = set(connection.execute(text("SELECT event_type FROM coeus_outbox")).scalars())
        audit_payload = str(
            connection.execute(
                text(
                    "SELECT metadata FROM coeus_audit_events "
                    "WHERE event_type='organisation_bootstrapped'"
                )
            ).scalar_one()
        )
    assert root == (plan.root_name, "bootstrap", 1)
    assert closure == (plan.root_unit_id, plan.root_unit_id, 0)
    assert actions == {action.value for action in ManagementAction}
    assert marker == (plan.command_id, plan.root_unit_id)
    assert evidence["organisation_bootstrapped"] == 1
    assert outbox == {"organisation_bootstrapped"}
    assert "nonce" not in audit_payload.lower()

    with pytest.raises(OrganisationBootstrapUnavailable):
        store.bootstrap(_plan())
    with engine.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM organisation_units")).scalar_one() == 1
        assert (
            connection.execute(
                text(
                    "SELECT count(*) FROM coeus_audit_events "
                    "WHERE event_type='organisation_bootstrap_denied'"
                )
            ).scalar_one()
            == 1
        )
    engine.dispose()


def test_concurrent_bootstrap_has_exactly_one_winner(postgres_database_url: str) -> None:
    _upgrade(postgres_database_url)
    engine = create_engine(postgres_database_url)
    store = PostgresOrganisationBootstrapStore(engine)
    plans = (_plan(), _plan())

    def attempt(plan: OrganisationBootstrapPlan) -> str:
        try:
            store.bootstrap(plan)
            return "created"
        except OrganisationBootstrapUnavailable:
            return "denied"

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = tuple(executor.map(attempt, plans))
    assert sorted(outcomes) == ["created", "denied"]
    with engine.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM organisation_units")).scalar_one() == 1
        assert (
            connection.execute(
                text("SELECT count(*) FROM organisation_bootstrap_state")
            ).scalar_one()
            == 1
        )
    engine.dispose()
