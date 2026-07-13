"""Checksummed PostgreSQL and local-object backup/restore drill."""

import shutil
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

import psycopg
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from coeus.persistence.backup_manifest import (
    BackupManifest,
    ObjectBackup,
    file_sha256,
    read_manifest,
    safe_relative_path,
    write_manifest,
)
from coeus.persistence.database_url import synchronous_database_url
from coeus.persistence.draft_audience_reconciliation import reconcile_draft_audiences
from coeus.persistence.postgres_logical_backup import export_tables, import_tables
from coeus.persistence.ticket_shadow_schema import validate_relational_ticket_rows


@dataclass(frozen=True)
class RestoreDrillReport:
    recovery_id: str
    alembic_revision: str
    table_count: int
    object_count: int


def create_backup_bundle(
    database_url: str,
    object_root: Path,
    bundle: Path,
    *,
    confirm_quiesced: bool,
) -> BackupManifest:
    if not confirm_quiesced:
        raise ValueError("Backup requires explicit writer quiescence confirmation.")
    if bundle.exists():
        raise ValueError("Backup bundle path already exists.")
    recovery_id = str(uuid4())
    staging = bundle.with_name(f".{bundle.name}.{recovery_id}.tmp")
    try:
        revision, tables = export_tables(database_url, staging)
        objects = _copy_objects(object_root, staging / "objects")
        _validate_asset_objects(database_url, objects)
        if _inventory(object_root) != objects:
            raise RuntimeError("Object storage changed during backup.")
        verification = staging / "verification"
        check_revision, check_tables = export_tables(database_url, verification)
        if revision != check_revision or tuple(item.sha256 for item in tables) != tuple(
            item.sha256 for item in check_tables
        ):
            raise RuntimeError("PostgreSQL durable state changed during backup.")
        shutil.rmtree(verification)
        manifest = BackupManifest(1, recovery_id, revision, tables, objects)
        write_manifest(staging / "manifest.json", manifest)
        staging.replace(bundle)
        return manifest
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def restore_backup_bundle(
    source_database_url: str,
    target_database_url: str,
    bundle: Path,
    target_object_root: Path,
    *,
    confirm_quiesced: bool,
) -> RestoreDrillReport:
    if not confirm_quiesced:
        raise ValueError("Restore requires explicit writer quiescence confirmation.")
    if _database_identity(source_database_url) == _database_identity(target_database_url):
        raise ValueError("Source and restore target databases must be different.")
    if target_object_root.exists() and any(target_object_root.iterdir()):
        raise ValueError("Restore target object directory must be empty.")
    manifest = read_manifest(bundle / "manifest.json")
    _verify_bundle(bundle, manifest)
    _upgrade_database(target_database_url)
    if _revision(target_database_url) != manifest.alembic_revision:
        raise RuntimeError("Restore target migration revision is incompatible with the bundle.")
    object_staging = target_object_root.with_name(
        f".{target_object_root.name}.{manifest.recovery_id}.tmp"
    )
    try:
        _restore_objects(bundle, object_staging, manifest.objects)
        import_tables(target_database_url, bundle, manifest.tables)
        _validate_restored_database(target_database_url, manifest.objects)
        if target_object_root.exists():
            target_object_root.rmdir()
        object_staging.replace(target_object_root)
    except Exception:
        shutil.rmtree(object_staging, ignore_errors=True)
        raise
    return RestoreDrillReport(
        manifest.recovery_id,
        manifest.alembic_revision,
        len(manifest.tables),
        len(manifest.objects),
    )


def _copy_objects(root: Path, target: Path) -> tuple[ObjectBackup, ...]:
    inventory = _inventory(root)
    target.mkdir(parents=True, exist_ok=False)
    for item in inventory:
        source = root / safe_relative_path(item.key)
        destination = target / safe_relative_path(item.key)
        destination.parent.mkdir(parents=True, exist_ok=True)
        with source.open("rb") as reader, destination.open("xb") as writer:
            shutil.copyfileobj(reader, writer, length=1024 * 1024)
    return inventory


def _inventory(root: Path) -> tuple[ObjectBackup, ...]:
    if not root.exists():
        return ()
    objects: list[ObjectBackup] = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ValueError("Object storage contains a symbolic link.")
        if not path.is_file():
            continue
        if path.name.startswith(".") and path.name.endswith(".tmp"):
            raise ValueError("Object storage contains an abandoned temporary file.")
        relative = path.relative_to(root).as_posix()
        safe_relative_path(relative)
        objects.append(ObjectBackup(relative, path.stat().st_size, file_sha256(path)))
    return tuple(objects)


def _verify_bundle(bundle: Path, manifest: BackupManifest) -> None:
    for table in manifest.tables:
        path = bundle / safe_relative_path(table.file)
        if not path.is_file() or file_sha256(path) != table.sha256:
            raise ValueError(f"Backup table file failed verification: {table.name}.")
    for item in manifest.objects:
        path = bundle / "objects" / safe_relative_path(item.key)
        if (
            not path.is_file()
            or path.stat().st_size != item.size_bytes
            or file_sha256(path) != item.sha256
        ):
            raise ValueError(f"Backup object failed verification: {item.key}.")


def _restore_objects(bundle: Path, staging: Path, objects: tuple[ObjectBackup, ...]) -> None:
    if staging.exists():
        raise ValueError("Restore object staging path already exists.")
    staging.mkdir(parents=True)
    for item in objects:
        source = bundle / "objects" / safe_relative_path(item.key)
        destination = staging / safe_relative_path(item.key)
        destination.parent.mkdir(parents=True, exist_ok=True)
        with source.open("rb") as reader, destination.open("xb") as writer:
            shutil.copyfileobj(reader, writer, length=1024 * 1024)
    if _inventory(staging) != objects:
        raise RuntimeError("Restored object inventory did not reconcile.")


def _validate_restored_database(database_url: str, objects: tuple[ObjectBackup, ...]) -> None:
    engine = create_engine(synchronous_database_url(database_url), pool_pre_ping=True)
    with engine.connect() as connection:
        validate_relational_ticket_rows(connection)
        leases = connection.execute(text("SELECT count(*) FROM coeus_resource_leases")).scalar_one()
        claims = connection.execute(
            text("SELECT count(*) FROM coeus_outbox WHERE claimed_by IS NOT NULL")
        ).scalar_one()
        if leases or claims:
            raise RuntimeError("Restore retained an ephemeral lease or outbox claim.")
    audience = reconcile_draft_audiences(database_url)
    if audience.missing or audience.extra:
        raise RuntimeError("Restored draft audiences do not reconcile.")
    _validate_asset_objects(database_url, objects)


def _validate_asset_objects(database_url: str, objects: tuple[ObjectBackup, ...]) -> None:
    expected = {item.key: (item.size_bytes, item.sha256) for item in objects}
    with psycopg.connect(_dsn(database_url)) as connection:
        rows = connection.execute(
            "SELECT object_key, size_bytes, sha256 FROM intelligence_store_assets"
        ).fetchall()
    actual = {str(key): (int(size), str(digest)) for key, size, digest in rows}
    if actual != expected:
        raise RuntimeError("Database assets and local object storage do not reconcile.")


def _upgrade_database(database_url: str) -> None:
    api_root = Path(__file__).resolve().parents[3]
    config = Config(str(api_root / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", synchronous_database_url(database_url))
    command.upgrade(config, "head")


def _revision(database_url: str) -> str:
    with psycopg.connect(_dsn(database_url)) as connection:
        row = connection.execute("SELECT version_num FROM alembic_version").fetchone()
        if row is None:
            raise RuntimeError("Restore target has no Alembic revision.")
        return str(row[0])


def _database_identity(database_url: str) -> tuple[object, ...]:
    url = make_url(database_url)
    return (url.host, url.port, url.database, url.username)


def _dsn(database_url: str) -> str:
    return make_url(database_url).set(drivername="postgresql").render_as_string(hide_password=False)
