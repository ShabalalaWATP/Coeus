from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace

import pytest

from coeus.persistence.backup_manifest import (
    BackupManifest,
    ObjectBackup,
    TableBackup,
    write_manifest,
)
from coeus.services import coordinated_restore as restore

SOURCE_URL = "postgresql+psycopg://user:password@localhost/source"
TARGET_URL = "postgresql+psycopg://user:password@localhost/target"


def _manifest(*, objects: tuple[ObjectBackup, ...] = ()) -> BackupManifest:
    return BackupManifest(1, "recovery-1", "revision-1", (), objects)


def test_backup_requires_quiescence_and_a_new_bundle(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="quiescence"):
        restore.create_backup_bundle(
            SOURCE_URL, tmp_path / "objects", tmp_path / "bundle", confirm_quiesced=False
        )
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    with pytest.raises(ValueError, match="already exists"):
        restore.create_backup_bundle(
            SOURCE_URL, tmp_path / "objects", bundle, confirm_quiesced=True
        )


def test_backup_cleans_staging_when_export_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        restore,
        "export_tables",
        lambda *_args: (_ for _ in ()).throw(RuntimeError("synthetic export failure")),
    )

    with pytest.raises(RuntimeError, match="synthetic export"):
        restore.create_backup_bundle(
            SOURCE_URL,
            tmp_path / "objects",
            tmp_path / "bundle",
            confirm_quiesced=True,
        )

    assert not tuple(tmp_path.glob(".bundle.*.tmp"))


def test_backup_rejects_database_or_object_changes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    table = TableBackup("coeus_state", ("namespace",), 0, "tables/state.copy", "a" * 64)

    def export(_url: str, root: Path) -> tuple[str, tuple[TableBackup, ...]]:
        root.mkdir(parents=True)
        return "revision-1", (table,)

    monkeypatch.setattr(restore, "export_tables", export)
    monkeypatch.setattr(restore, "_copy_objects", lambda *_args: ())
    monkeypatch.setattr(restore, "_validate_asset_objects", lambda *_args: None)
    monkeypatch.setattr(
        restore,
        "_inventory",
        lambda _root: (ObjectBackup("changed.bin", 1, "b" * 64),),
    )
    with pytest.raises(RuntimeError, match="Object storage changed"):
        restore.create_backup_bundle(
            SOURCE_URL,
            tmp_path / "objects",
            tmp_path / "object-drift",
            confirm_quiesced=True,
        )

    calls = 0

    def changing_export(_url: str, root: Path) -> tuple[str, tuple[TableBackup, ...]]:
        nonlocal calls
        root.mkdir(parents=True)
        calls += 1
        digest = "a" * 64 if calls == 1 else "b" * 64
        return "revision-1", (
            TableBackup(table.name, table.columns, table.row_count, table.file, digest),
        )

    monkeypatch.setattr(restore, "export_tables", changing_export)
    monkeypatch.setattr(restore, "_inventory", lambda _root: ())
    with pytest.raises(RuntimeError, match="durable state changed"):
        restore.create_backup_bundle(
            SOURCE_URL,
            tmp_path / "objects",
            tmp_path / "database-drift",
            confirm_quiesced=True,
        )


def test_restore_rejects_unsafe_targets_and_revision_mismatch(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    write_manifest(bundle / "manifest.json", _manifest())
    with pytest.raises(ValueError, match="quiescence"):
        restore.restore_backup_bundle(
            SOURCE_URL, TARGET_URL, bundle, tmp_path / "objects", confirm_quiesced=False
        )
    with pytest.raises(ValueError, match="must be different"):
        restore.restore_backup_bundle(
            SOURCE_URL, SOURCE_URL, bundle, tmp_path / "objects", confirm_quiesced=True
        )
    nonempty = tmp_path / "nonempty"
    nonempty.mkdir()
    nonempty.joinpath("evidence").write_text("x", encoding="utf-8")
    with pytest.raises(ValueError, match="must be empty"):
        restore.restore_backup_bundle(
            SOURCE_URL, TARGET_URL, bundle, nonempty, confirm_quiesced=True
        )

    monkeypatch.setattr(restore, "_upgrade_database", lambda _url: None)
    monkeypatch.setattr(restore, "_revision", lambda _url: "different-revision")
    with pytest.raises(RuntimeError, match="incompatible"):
        restore.restore_backup_bundle(
            SOURCE_URL,
            TARGET_URL,
            bundle,
            tmp_path / "revision-target",
            confirm_quiesced=True,
        )


def test_restore_cleans_object_staging_after_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    write_manifest(bundle / "manifest.json", _manifest())
    target = tmp_path / "target"
    monkeypatch.setattr(restore, "_upgrade_database", lambda _url: None)
    monkeypatch.setattr(restore, "_revision", lambda _url: "revision-1")

    def fail_restore(_bundle: Path, staging: Path, _objects: object) -> None:
        staging.mkdir()
        staging.joinpath("partial").write_bytes(b"partial")
        raise RuntimeError("synthetic import failure")

    monkeypatch.setattr(restore, "_restore_objects", fail_restore)

    with pytest.raises(RuntimeError, match="synthetic import"):
        restore.restore_backup_bundle(SOURCE_URL, TARGET_URL, bundle, target, confirm_quiesced=True)

    assert not tuple(tmp_path.glob(".target.*.tmp"))


def test_restore_replaces_an_existing_empty_object_root(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    write_manifest(bundle / "manifest.json", _manifest())
    target = tmp_path / "target"
    target.mkdir()
    monkeypatch.setattr(restore, "_upgrade_database", lambda _url: None)
    monkeypatch.setattr(restore, "_revision", lambda _url: "revision-1")
    monkeypatch.setattr(restore, "import_tables", lambda *_args: None)
    monkeypatch.setattr(restore, "_validate_restored_database", lambda *_args: None)

    report = restore.restore_backup_bundle(
        SOURCE_URL, TARGET_URL, bundle, target, confirm_quiesced=True
    )

    assert report.recovery_id == "recovery-1"
    assert target.is_dir()


def test_inventory_and_object_restore_reject_unsafe_state(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    root.joinpath(".abandoned.tmp").write_bytes(b"partial")
    with pytest.raises(ValueError, match="temporary"):
        restore._inventory(root)

    bundle = tmp_path / "bundle"
    object_root = bundle / "objects"
    object_root.mkdir(parents=True)
    payload = b"synthetic bytes"
    object_root.joinpath("evidence.bin").write_bytes(payload)
    item = ObjectBackup("evidence.bin", len(payload), sha256(payload).hexdigest())
    staging = tmp_path / "staging"
    restore._restore_objects(bundle, staging, (item,))
    assert staging.joinpath("evidence.bin").read_bytes() == payload
    with pytest.raises(ValueError, match="already exists"):
        restore._restore_objects(bundle, staging, (item,))


def test_inventory_rejects_symbolic_links(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    root.joinpath("link").write_bytes(b"not a real link")
    original = Path.is_symlink
    monkeypatch.setattr(
        Path,
        "is_symlink",
        lambda path: path.name == "link" or original(path),
    )

    with pytest.raises(ValueError, match="symbolic link"):
        restore._inventory(root)


def test_restored_object_inventory_must_reconcile(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    monkeypatch.setattr(
        restore,
        "_inventory",
        lambda _root: (ObjectBackup("unexpected", 0, "a" * 64),),
    )

    with pytest.raises(RuntimeError, match="inventory"):
        restore._restore_objects(bundle, tmp_path / "staging", ())


def test_bundle_verification_checks_object_size_and_digest(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    object_root = bundle / "objects"
    object_root.mkdir(parents=True)
    object_root.joinpath("evidence.bin").write_bytes(b"wrong")
    manifest = _manifest(objects=(ObjectBackup("evidence.bin", 3, "a" * 64),))

    with pytest.raises(ValueError, match="object failed verification"):
        restore._verify_bundle(bundle, manifest)


@pytest.mark.parametrize(("leases", "claims"), [(1, 0), (0, 1)])
def test_restored_database_rejects_ephemeral_state(
    monkeypatch: pytest.MonkeyPatch, leases: int, claims: int
) -> None:
    values = iter((leases, claims))

    class Result:
        def scalar_one(self) -> int:
            return next(values)

    class Connection:
        def __enter__(self) -> "Connection":
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def execute(self, _statement: object) -> Result:
            return Result()

    class Engine:
        def connect(self) -> Connection:
            return Connection()

    monkeypatch.setattr(restore, "create_engine", lambda *_args, **_kwargs: Engine())
    monkeypatch.setattr(restore, "validate_relational_ticket_rows", lambda _connection: None)

    with pytest.raises(RuntimeError, match="ephemeral"):
        restore._validate_restored_database(TARGET_URL, ())


def test_restored_database_rejects_audience_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Result:
        def scalar_one(self) -> int:
            return 0

    class Connection:
        def __enter__(self) -> "Connection":
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def execute(self, _statement: object) -> Result:
            return Result()

    class Engine:
        def connect(self) -> Connection:
            return Connection()

    monkeypatch.setattr(restore, "create_engine", lambda *_args, **_kwargs: Engine())
    monkeypatch.setattr(restore, "validate_relational_ticket_rows", lambda _connection: None)
    monkeypatch.setattr(
        restore,
        "reconcile_draft_audiences",
        lambda _url: SimpleNamespace(missing=("missing",), extra=()),
    )

    with pytest.raises(RuntimeError, match="audiences"):
        restore._validate_restored_database(TARGET_URL, ())


def test_asset_reconciliation_and_revision_checks_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Result:
        def fetchall(self) -> list[tuple[str, int, str]]:
            return [("unexpected.bin", 1, "a" * 64)]

        def fetchone(self) -> None:
            return None

    class Connection:
        def __enter__(self) -> "Connection":
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def execute(self, _statement: object) -> Result:
            return Result()

    monkeypatch.setattr(restore.psycopg, "connect", lambda *_args, **_kwargs: Connection())

    with pytest.raises(RuntimeError, match="object storage"):
        restore._validate_asset_objects(TARGET_URL, ())
    with pytest.raises(RuntimeError, match="no Alembic revision"):
        restore._revision(TARGET_URL)
