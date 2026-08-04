"""Coordinated recovery evidence for the Sprint 24 relational authority model."""

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import psycopg
import pytest
from backup_restore_database_support import dsn, second_database, seed_fixture, upgrade_database
from backup_restore_follow_on_support import (
    CUTOVER_TABLES,
    DEDUPLICATION_KEY,
    FIXTURE_TABLES,
    SPRINT_24_PREFIXES,
    SPRINT_24_TABLES,
    restored_deduplication_key,
)
from psycopg import sql
from sqlalchemy import create_engine, text

from coeus.domain.jioc_routing import ROUTING_RELATIONAL_CAPACITY_RELEASE
from coeus.persistence.backup_manifest import TableBackup
from coeus.persistence.cutover_activation_postgres import PostgresCutoverActivationStore
from coeus.persistence.postgres_backup_tables import TABLES
from coeus.persistence.postgres_logical_backup import (
    export_tables,
    security_authority_fence,
)
from coeus.services import coordinated_restore as recovery
from coeus.services.coordinated_restore import create_backup_bundle, restore_backup_bundle

pytestmark = pytest.mark.postgres


def test_full_sprint24_fixture_restores_with_exact_counts_and_hashes(
    postgres_database_url: str, tmp_path: Path
) -> None:
    seed_fixture(postgres_database_url)
    with psycopg.connect(dsn(postgres_database_url)) as connection:
        schema_tables = {
            str(row[0])
            for row in connection.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema=current_schema()"
            )
            if str(row[0]).startswith(SPRINT_24_PREFIXES)
        }
    assert schema_tables == SPRINT_24_TABLES
    bundle = tmp_path / "bundle"
    manifest = create_backup_bundle(
        postgres_database_url,
        tmp_path / "source-objects",
        bundle,
        confirm_quiesced=True,
    )
    assert tuple(item.name for item in manifest.tables) == tuple(spec.name for spec in TABLES)
    assert {item.name for item in manifest.tables}.issuperset(SPRINT_24_TABLES)
    fixture_counts = {
        item.name: item.row_count for item in manifest.tables if item.name in FIXTURE_TABLES
    }
    assert fixture_counts.keys() == FIXTURE_TABLES
    assert all(fixture_counts.values())
    assert CUTOVER_TABLES.issubset(fixture_counts)

    source_eligible = PostgresCutoverActivationStore(
        create_engine(postgres_database_url)
    ).active_candidate_is_eligible(
        "1" * 64,
        "synthetic-revision",
        ROUTING_RELATIONAL_CAPACITY_RELEASE,
    )
    with second_database(postgres_database_url) as target_url:
        restore_backup_bundle(
            postgres_database_url,
            target_url,
            bundle,
            tmp_path / "target-objects",
            confirm_quiesced=True,
        )
        _, restored = export_tables(target_url, tmp_path / "restored-export")
        deduplication_key = restored_deduplication_key(target_url)
        cutover_eligible = PostgresCutoverActivationStore(
            create_engine(target_url)
        ).active_candidate_is_eligible(
            "1" * 64,
            "synthetic-revision",
            ROUTING_RELATIONAL_CAPACITY_RELEASE,
        )
        with (
            psycopg.connect(dsn(target_url)) as connection,
            pytest.raises(
                psycopg.errors.ObjectNotInPrerequisiteState,
                match="cutover evidence is immutable",
            ),
        ):
            connection.execute(
                "UPDATE organisation_cutover_manifests SET backup_restore_hash=repeat('0',64)"
            )

    assert tuple((item.name, item.row_count, item.sha256) for item in restored) == tuple(
        (item.name, item.row_count, item.sha256) for item in manifest.tables
    )
    assert deduplication_key == DEDUPLICATION_KEY
    # The fixture records placeholder parity digests, so the candidate is not
    # activatable. What recovery must preserve is the verdict itself: a restored
    # database has to reach the same answer from the same evidence.
    assert cutover_eligible == source_eligible


def test_restore_invalidates_every_login_session(
    postgres_database_url: str, tmp_path: Path
) -> None:
    upgrade_database(postgres_database_url)
    with psycopg.connect(dsn(postgres_database_url)) as connection:
        connection.execute(
            "INSERT INTO coeus_state(namespace,payload) VALUES "
            '(\'sessions\',\'{"sessions":[{"token_hash":"synthetic"}]}\'::jsonb) '
            "ON CONFLICT(namespace) DO UPDATE SET payload=EXCLUDED.payload,updated_at=now()"
        )
        connection.commit()
    bundle = tmp_path / "bundle"
    create_backup_bundle(
        postgres_database_url,
        tmp_path / "source-objects",
        bundle,
        confirm_quiesced=True,
    )
    with second_database(postgres_database_url) as target_url:
        restore_backup_bundle(
            postgres_database_url,
            target_url,
            bundle,
            tmp_path / "target-objects",
            confirm_quiesced=True,
        )
        with psycopg.connect(dsn(target_url)) as connection:
            row = connection.execute(
                "SELECT payload FROM coeus_state WHERE namespace='sessions'"
            ).fetchone()
            assert row is not None
            payload = row[0]
    assert payload == {"sessions": []}


@pytest.mark.parametrize("change", ["grant_revoked", "account_suspended", "ownership_moved"])
def test_restore_fails_closed_when_security_authority_changed_after_backup(
    postgres_database_url: str, tmp_path: Path, change: str
) -> None:
    actor_id = seed_fixture(postgres_database_url)
    bundle = tmp_path / "bundle"
    create_backup_bundle(
        postgres_database_url,
        tmp_path / "source-objects",
        bundle,
        confirm_quiesced=True,
    )
    engine = create_engine(postgres_database_url)
    with engine.begin() as connection:
        if change == "grant_revoked":
            connection.execute(
                text(
                    "UPDATE team_management_grants SET revoked_at=now(),version=version+1,"
                    "updated_at=now(),revoked_by_user_id=:actor,revocation_reason='Recovery test' "
                    "WHERE grant_id=(SELECT grant_id FROM team_management_grants "
                    "WHERE revoked_at IS NULL ORDER BY delegation_depth,grant_id LIMIT 1)"
                ),
                {"actor": actor_id},
            )
        elif change == "account_suspended":
            connection.execute(
                text(
                    "UPDATE identity_account_projection SET is_active=false,credential_version="
                    "credential_version+1,projected_at=now() WHERE user_id=:actor"
                ),
                {"actor": actor_id},
            )
        else:
            connection.execute(
                text(
                    "UPDATE team_task_ownership SET owning_unit_id=(SELECT unit_id "
                    "FROM organisation_units WHERE unit_id<>team_task_ownership.owning_unit_id "
                    "ORDER BY unit_id LIMIT 1),version=version+1,updated_at=now() "
                    "WHERE ownership_id=(SELECT ownership_id FROM team_task_ownership LIMIT 1)"
                )
            )

    with second_database(postgres_database_url) as target_url:
        with pytest.raises(RuntimeError, match="Security authority changed after backup"):
            restore_backup_bundle(
                postgres_database_url,
                target_url,
                bundle,
                tmp_path / "target-objects",
                confirm_quiesced=True,
            )
        with psycopg.connect(dsn(target_url)) as connection:
            target_row = connection.execute("SELECT to_regclass('alembic_version')").fetchone()
            assert target_row is not None and target_row[0] is None


def test_security_fence_blocks_authority_writes_until_promotion(
    postgres_database_url: str, tmp_path: Path
) -> None:
    seed_fixture(postgres_database_url)
    bundle = tmp_path / "bundle"
    manifest = create_backup_bundle(
        postgres_database_url,
        tmp_path / "source-objects",
        bundle,
        confirm_quiesced=True,
    )
    with (
        security_authority_fence(postgres_database_url, manifest.tables),
        psycopg.connect(dsn(postgres_database_url)) as writer,
    ):
        writer.execute("SET statement_timeout='250ms'")
        with pytest.raises(psycopg.errors.QueryCanceled):
            writer.execute(
                "UPDATE team_task_ownership SET version=version+1 "
                "WHERE ownership_id=(SELECT ownership_id FROM team_task_ownership LIMIT 1)"
            )


def test_failed_post_import_validation_quarantines_target(
    postgres_database_url: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed_fixture(postgres_database_url)
    bundle = tmp_path / "bundle"
    create_backup_bundle(
        postgres_database_url,
        tmp_path / "source-objects",
        bundle,
        confirm_quiesced=True,
    )

    def fail_validation(*_args: object) -> None:
        raise RuntimeError("synthetic post-import failure")

    monkeypatch.setattr(recovery, "_validate_restored_database", fail_validation)
    with second_database(postgres_database_url) as target_url:
        with pytest.raises(RuntimeError, match="synthetic post-import failure"):
            restore_backup_bundle(
                postgres_database_url,
                target_url,
                bundle,
                tmp_path / "target-objects",
                confirm_quiesced=True,
            )
        with psycopg.connect(dsn(target_url)) as connection:
            counts = []
            for spec in TABLES:
                row = connection.execute(
                    sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(spec.name))
                ).fetchone()
                assert row is not None
                counts.append(int(row[0]))
    assert not any(counts)


def test_failed_fence_exit_quarantines_published_restore(
    postgres_database_url: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed_fixture(postgres_database_url)
    bundle = tmp_path / "bundle"
    create_backup_bundle(
        postgres_database_url,
        tmp_path / "source-objects",
        bundle,
        confirm_quiesced=True,
    )

    @contextmanager
    def lost_fence(database_url: str, backups: tuple[TableBackup, ...]) -> Iterator[None]:
        with security_authority_fence(database_url, backups):
            yield
        raise RuntimeError("synthetic fence connection loss")

    monkeypatch.setattr(recovery, "security_authority_fence", lost_fence)
    target_objects = tmp_path / "target-objects"
    with second_database(postgres_database_url) as target_url:
        with pytest.raises(RuntimeError, match="synthetic fence connection loss"):
            restore_backup_bundle(
                postgres_database_url,
                target_url,
                bundle,
                target_objects,
                confirm_quiesced=True,
            )
        with psycopg.connect(dsn(target_url)) as connection:
            for spec in TABLES:
                row = connection.execute(
                    sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(spec.name))
                ).fetchone()
                assert row is not None and int(row[0]) == 0
    assert not target_objects.exists()
