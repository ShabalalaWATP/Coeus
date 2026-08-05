"""PostgreSQL evidence for synthetic workforce integrity and exact repair."""

from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

from coeus.core.config import Settings
from coeus.domain.synthetic_organisation_fixture import (
    SyntheticFixtureCommand,
    SyntheticFixtureConflict,
    SyntheticFixtureUser,
)
from coeus.persistence.synthetic_fixture_live_integrity import inspect_live_synthetic_fixture
from coeus.persistence.synthetic_organisation_fixture_postgres import (
    PostgresSyntheticOrganisationFixtureStore,
)
from coeus.repositories.access import SeedAccessRepository
from coeus.repositories.auth import SeedUserRepository
from coeus.repositories.auth_seed import seed_user_specs
from coeus.repositories.synthetic_organisation_manifest import synthetic_posting_specs
from coeus.repositories.synthetic_workforce import synthetic_user_id

API_ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.postgres


class _Hasher:
    def hash(self, credential: str) -> str:
        return f"hash:{credential}"

    def verify(self, stored_hash: str, credential: str) -> bool:
        return stored_hash == self.hash(credential)

    def needs_rehash(self, stored_hash: str) -> bool:
        return False


def _upgrade(database_url: str) -> None:
    config = Config(str(API_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "head")


def _fixture_users() -> tuple[SyntheticFixtureUser, ...]:
    active = {item.username: item.is_active for item in seed_user_specs()}
    return tuple(
        SyntheticFixtureUser(username, synthetic_user_id(username), active[username])
        for username in dict.fromkeys(item.username for item in synthetic_posting_specs())
    )


def _apply(store: PostgresSyntheticOrganisationFixtureStore) -> None:
    actor_id = synthetic_user_id("admin@example.test")
    users = _fixture_users()
    preview = store.preview(actor_id, users)
    store.apply(
        SyntheticFixtureCommand(
            uuid4(), "workforce-hardening-apply", actor_id, preview.preview_hash
        ),
        users,
    )


def test_live_integrity_report_covers_authority_workload_and_transfer(
    postgres_database_url: str,
) -> None:
    _upgrade(postgres_database_url)
    engine = create_engine(postgres_database_url)
    store = PostgresSyntheticOrganisationFixtureStore(engine)
    _apply(store)
    users = SeedUserRepository(Settings(environment="test"), _Hasher())
    access = SeedAccessRepository(users)
    with engine.connect() as connection:
        report = inspect_live_synthetic_fixture(connection, access)
    assert report.valid, report.errors
    assert report.maximum_active_packages_per_analyst == 1
    assert report.missing_reservations == 0
    assert report.acg_authorisation_gaps == 0
    assert report.transfer_evidence_gaps == 0
    assert report.suspended_account_gaps == 0
    engine.dispose()


def test_reconcile_repairs_only_exact_fixture_identifiers(
    postgres_database_url: str,
) -> None:
    _upgrade(postgres_database_url)
    engine = create_engine(postgres_database_url)
    store = PostgresSyntheticOrganisationFixtureStore(engine)
    _apply(store)
    actor_id = synthetic_user_id("admin@example.test")
    users = _fixture_users()
    local_id = uuid4()
    with engine.begin() as connection:
        canonical_root = connection.execute(
            text("SELECT unit_id FROM organisation_units WHERE short_name='DI'")
        ).scalar_one()
        connection.execute(
            text("UPDATE organisation_units SET name='Drifted fixture name' WHERE unit_id=:id"),
            {"id": canonical_root},
        )
        connection.execute(
            text(
                "INSERT INTO organisation_units(unit_id,name,short_name,category,parent_unit_id,"
                "is_active,valid_from,time_zone,description,provenance,version) VALUES "
                "(:id,'Local Addition','LOCAL-ADD','customer_team',:parent,true,now(),"
                "'Europe/London','Local operator-owned row.','manual',1)"
            ),
            {"id": local_id, "parent": canonical_root},
        )
        connection.execute(
            text(
                "INSERT INTO organisation_unit_closure(ancestor_unit_id,descendant_unit_id,depth) "
                "SELECT ancestor_unit_id,:local_id,depth+1 FROM organisation_unit_closure "
                "WHERE descendant_unit_id=:root_id UNION ALL SELECT :local_id,:local_id,0"
            ),
            {"local_id": local_id, "root_id": canonical_root},
        )
    preview = store.preview(actor_id, users)
    assert {item.code for item in preview.findings} == {"fixture_row_changed"}
    command_value = SyntheticFixtureCommand(
        uuid4(), "workforce-hardening-reconcile", actor_id, preview.preview_hash
    )
    result = store.reconcile(command_value, users)
    assert result.reconciled_rows == 1
    assert store.reconcile(command_value, users).replayed
    with engine.connect() as connection:
        assert (
            connection.execute(
                text("SELECT name FROM organisation_units WHERE unit_id=:id"), {"id": local_id}
            ).scalar_one()
            == "Local Addition"
        )
        assert (
            connection.execute(
                text("SELECT name FROM organisation_units WHERE short_name='DI'")
            ).scalar_one()
            == "Defence Intelligence"
        )
    with engine.begin() as connection:
        connection.execute(
            text("UPDATE organisation_units SET provenance='manual' WHERE short_name='DI'")
        )
    collision = store.preview(actor_id, users)
    assert {item.code for item in collision.findings} == {"fixture_identifier_collision"}
    with pytest.raises(SyntheticFixtureConflict, match="contains conflicts"):
        store.reconcile(
            SyntheticFixtureCommand(
                uuid4(), "workforce-collision-refusal", actor_id, collision.preview_hash
            ),
            users,
        )
    engine.dispose()
