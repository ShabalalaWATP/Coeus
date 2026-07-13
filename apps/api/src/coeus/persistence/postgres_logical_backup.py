"""Allow-listed PostgreSQL binary COPY export and import."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import psycopg
from psycopg import sql
from sqlalchemy.engine import make_url

from coeus.persistence.backup_manifest import TableBackup, file_sha256, safe_relative_path


@dataclass(frozen=True)
class TableSpec:
    name: str
    columns: tuple[str, ...]
    order_by: tuple[str, ...]


TABLES = (
    TableSpec("coeus_state", ("namespace", "payload", "updated_at"), ("namespace",)),
    TableSpec(
        "coeus_audit_events",
        ("event_id", "event_type", "occurred_at", "actor_user_id", "metadata"),
        ("occurred_at", "event_id"),
    ),
    TableSpec(
        "coeus_ticket_aggregates",
        (
            "ticket_id",
            "requester_user_id",
            "state",
            "consumes_capacity",
            "version",
            "payload",
            "canonical_hash",
            "updated_at",
        ),
        ("ticket_id",),
    ),
    TableSpec(
        "coeus_outbox",
        (
            "event_id",
            "aggregate_id",
            "aggregate_version",
            "event_type",
            "payload",
            "created_at",
            "available_at",
            "attempt_count",
            "claimed_by",
            "claim_expires_at",
            "last_error",
            "delivered_at",
            "dead_lettered_at",
        ),
        ("event_id",),
    ),
    TableSpec(
        "coeus_draft_audiences",
        ("product_id", "principal_id", "reason", "ticket_id", "updated_at"),
        ("product_id", "principal_id", "reason", "ticket_id"),
    ),
    TableSpec(
        "intelligence_store_products",
        (
            "product_id",
            "reference",
            "title",
            "summary",
            "description",
            "product_type",
            "source_type",
            "owner_team",
            "area_or_region",
            "classification_level",
            "releasability",
            "handling_caveats",
            "tags",
            "semantic_labels",
            "acg_ids",
            "status",
            "time_period_start",
            "time_period_end",
            "geojson_ref",
            "bounding_box",
            "created_by_user_id",
            "created_at",
            "updated_at",
            "search_document",
            "embedding",
            "embedding_source_hash",
        ),
        ("product_id",),
    ),
    TableSpec(
        "intelligence_store_assets",
        (
            "asset_id",
            "product_id",
            "name",
            "asset_type",
            "mime_type",
            "size_bytes",
            "sha256",
            "object_key",
            "preview_kind",
            "created_at",
        ),
        ("asset_id",),
    ),
    TableSpec(
        "intelligence_store_product_acgs",
        ("product_id", "acg_id"),
        ("product_id", "acg_id"),
    ),
    TableSpec(
        "intelligence_store_semantic_labels",
        ("product_id", "label"),
        ("product_id", "label"),
    ),
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
        for spec, backup in zip(TABLES, backups, strict=True):
            _require_table(connection, spec.name)
            count = _table_count(connection, spec.name, operation="restore preflight")
            if count:
                raise RuntimeError(f"Restore target table {spec.name} is not empty.")
            _copy_in(connection, spec, bundle / safe_relative_path(backup.file))
            restored = _table_count(connection, spec.name, operation="restore verification")
            if restored != backup.row_count:
                raise RuntimeError(f"Restore row count differs for {spec.name}.")
        connection.execute("DELETE FROM coeus_resource_leases")
        connection.execute(
            "UPDATE coeus_outbox SET claimed_by=NULL, claim_expires_at=NULL, "
            "available_at=LEAST(available_at, now()) "
            "WHERE delivered_at IS NULL AND dead_lettered_at IS NULL"
        )


def database_name(database_url: str) -> str:
    return str(make_url(database_url).database)


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
    # Names come only from TABLES and psycopg Identifier quotes them. This is
    # not SQLAlchemy or raw interpolation, despite the generic Semgrep match.
    # nosemgrep
    row = connection.execute(
        sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(table))
    ).fetchone()
    if row is None:
        raise RuntimeError(f"Could not count {operation} table {table}.")
    return int(row[0])


def _dsn(database_url: str) -> str:
    return make_url(database_url).set(drivername="postgresql").render_as_string(hide_password=False)
