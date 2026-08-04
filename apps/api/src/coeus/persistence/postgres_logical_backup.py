"""Allow-listed PostgreSQL binary COPY export and import."""

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import psycopg
from psycopg import sql
from sqlalchemy.engine import make_url

from coeus.persistence.backup_manifest import TableBackup, file_sha256, safe_relative_path
from coeus.persistence.postgres_backup_table_spec import TableSpec
from coeus.persistence.postgres_backup_tables import TABLES

_SECURITY_AUTHORITY_TABLES = frozenset(
    {
        "calendar_event_scopes",
        "calendar_events",
        "calendar_commitment_notifications",
        "calendar_commitment_responses",
        "canonical_work_packages",
        "coeus_draft_audiences",
        "coeus_state",
        "coeus_ticket_aggregates",
        "effective_authority_epochs",
        "identity_account_projection",
        "intelligence_store_product_acgs",
        "intelligence_store_products",
        "organisation_topology_revisions",
        "organisation_cutover_approvals",
        "organisation_cutover_checkpoint_events",
        "organisation_cutover_checkpoints",
        "organisation_cutover_evidence",
        "organisation_cutover_manifests",
        "organisation_cutover_recovery_events",
        "organisation_cutover_release",
        "organisation_cutover_slice_state",
        "organisation_cutover_writer_fences",
        "organisation_unit_closure",
        "organisation_units",
        "team_management_grants",
        "team_memberships",
        "team_task_ownership",
        "team_workspace_policies",
        "work_package_participants",
        "workflow_leg_transfer_commands",
        "workflow_leg_transfer_packages",
        "workflow_leg_transfer_team_holds",
        "workflow_leg_transfers",
        "workspace_delivery_preferences",
        "workspace_export_jobs",
        "workspace_productivity_commands",
        "workspace_saved_views",
        "workspace_store_links",
        "workspace_work_updates",
        "team_work_templates",
    }
)


def export_tables(database_url: str, root: Path) -> tuple[str, tuple[TableBackup, ...]]:
    root.mkdir(parents=True, exist_ok=False)
    backups: list[TableBackup] = []
    with psycopg.connect(_dsn(database_url), autocommit=True) as connection:
        connection.execute("BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        revision_row = connection.execute("SELECT version_num FROM alembic_version").fetchone()
        if revision_row is None:
            raise RuntimeError("Source database has no Alembic revision.")
        revision = str(revision_row[0])
        for spec in TABLES:
            _require_table(connection, spec.name)
            row_count = _table_count(connection, spec.name, operation="export")
            relative = f"tables/{spec.name}.copy"
            path = root / safe_relative_path(relative)
            path.parent.mkdir(parents=True, exist_ok=True)
            _copy_out(connection, spec, path)
            backups.append(
                TableBackup(spec.name, spec.columns, row_count, relative, file_sha256(path))
            )
        connection.rollback()
    return revision, tuple(backups)


def import_tables(database_url: str, bundle: Path, backups: tuple[TableBackup, ...]) -> None:
    _validate_specs(backups)
    with psycopg.connect(_dsn(database_url)) as connection, connection.transaction():
        connection.execute("SET CONSTRAINTS ALL DEFERRED")
        for spec, backup in zip(TABLES, backups, strict=True):
            _require_table(connection, spec.name)
            count = _table_count(connection, spec.name, operation="restore preflight")
            if count:
                raise RuntimeError(f"Restore target table {spec.name} is not empty.")
            _copy_in(connection, spec, bundle / safe_relative_path(backup.file))
            restored = _table_count(connection, spec.name, operation="restore verification")
            if restored != backup.row_count:
                raise RuntimeError(f"Restore row count differs for {spec.name}.")
        _verify_restored_hashes(connection, bundle, backups)
        connection.execute("DELETE FROM coeus_resource_leases")
        connection.execute(
            "UPDATE coeus_state SET payload='{\"sessions\":[]}'::jsonb,updated_at=now() "
            "WHERE namespace='sessions' AND payload<>'{\"sessions\":[]}'::jsonb"
        )
        connection.execute(
            "UPDATE coeus_outbox SET claimed_by=NULL, claim_expires_at=NULL, "
            "available_at=LEAST(available_at, now()) "
            "WHERE delivered_at IS NULL AND dead_lettered_at IS NULL"
        )


@contextmanager
def security_authority_fence(database_url: str, backups: tuple[TableBackup, ...]) -> Iterator[None]:
    """Hold source authority tables against writes through restore promotion."""
    _validate_specs(backups)
    by_name = {backup.name: backup for backup in backups}
    specs = tuple(spec for spec in TABLES if spec.name in _SECURITY_AUTHORITY_TABLES)
    with TemporaryDirectory(prefix="coeus-authority-fence-") as temporary:
        root = Path(temporary)
        with psycopg.connect(_dsn(database_url)) as connection, connection.transaction():
            connection.execute("SET LOCAL lock_timeout = '5s'")
            identifiers = sql.SQL(",").join(sql.Identifier(spec.name) for spec in specs)
            connection.execute(sql.SQL("LOCK TABLE {} IN SHARE MODE").format(identifiers))
            for spec in specs:
                path = root / f"{spec.name}.copy"
                _copy_out(connection, spec, path)
                if file_sha256(path) != by_name[spec.name].sha256:
                    raise RuntimeError(
                        "Security authority changed after backup; restore requires an "
                        "approved revocation replay checkpoint."
                    )
            yield


def clear_restored_tables(database_url: str) -> None:
    """Remove imported authority when a disposable restore target fails."""
    with psycopg.connect(_dsn(database_url)) as connection, connection.transaction():
        identifiers = sql.SQL(",").join(
            [
                *(sql.Identifier(spec.name) for spec in TABLES),
                sql.Identifier("coeus_resource_leases"),
            ]
        )
        connection.execute(sql.SQL("TRUNCATE TABLE {} CASCADE").format(identifiers))


def _copy_out(connection: psycopg.Connection[Any], spec: TableSpec, path: Path) -> None:
    columns = sql.SQL(",").join(map(sql.Identifier, spec.columns))
    order = sql.SQL(",").join(map(sql.Identifier, spec.order_by))
    statement = sql.SQL("COPY (SELECT {} FROM {} ORDER BY {}) TO STDOUT (FORMAT BINARY)").format(
        columns, sql.Identifier(spec.name), order
    )
    with path.open("wb") as stream, connection.cursor().copy(statement) as copy:
        while data := copy.read():
            stream.write(data)


def _copy_in(connection: psycopg.Connection[Any], spec: TableSpec, path: Path) -> None:
    columns = sql.SQL(",").join(map(sql.Identifier, spec.columns))
    statement = sql.SQL("COPY {} ({}) FROM STDIN (FORMAT BINARY)").format(
        sql.Identifier(spec.name), columns
    )
    with path.open("rb") as stream, connection.cursor().copy(statement) as copy:
        while chunk := stream.read(1024 * 1024):
            copy.write(chunk)


def _verify_restored_hashes(
    connection: psycopg.Connection[Any],
    bundle: Path,
    backups: tuple[TableBackup, ...],
) -> None:
    with TemporaryDirectory(prefix="coeus-restore-check-") as temporary:
        root = Path(temporary)
        for spec, backup in zip(TABLES, backups, strict=True):
            restored = root / f"{spec.name}.copy"
            _copy_out(connection, spec, restored)
            source = bundle / safe_relative_path(backup.file)
            if file_sha256(restored) != backup.sha256 or file_sha256(source) != backup.sha256:
                raise RuntimeError(f"Restore content hash differs for {spec.name}.")


def _validate_specs(backups: tuple[TableBackup, ...]) -> None:
    if len(backups) != len(TABLES):
        raise ValueError("Backup manifest table allow-list differs from this release.")
    for spec, backup in zip(TABLES, backups, strict=True):
        if backup.name != spec.name or backup.columns != spec.columns:
            raise ValueError("Backup manifest table schema differs from this release.")


def _require_table(connection: psycopg.Connection[Any], table: str) -> None:
    row = connection.execute("SELECT to_regclass(%s)", (table,)).fetchone()
    if row is None or row[0] is None:
        raise RuntimeError(f"Required recovery table {table} does not exist.")


def _table_count(connection: psycopg.Connection[Any], table: str, *, operation: str) -> int:
    if table not in {spec.name for spec in TABLES}:
        raise ValueError(f"Table {table} is not in the recovery allow-list.")
    row = connection.execute(
        sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(table))
    ).fetchone()
    if row is None:
        raise RuntimeError(f"Could not count {operation} table {table}.")
    return int(row[0])


def _dsn(database_url: str) -> str:
    return make_url(database_url).set(drivername="postgresql").render_as_string(hide_password=False)
