"""Containment checks for coordinated recovery bundles."""

import os
from contextlib import nullcontext
from hashlib import sha256
from pathlib import Path

import pytest

from coeus.persistence.backup_manifest import (
    BackupManifest,
    ObjectBackup,
    TableBackup,
    write_manifest,
)
from coeus.services import coordinated_restore as restore


@pytest.mark.parametrize("kind", ["table", "object", "parent"])
def test_bundle_symlinks_fail_closed(tmp_path: Path, kind: str) -> None:
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    outside = tmp_path / "outside.bin"
    outside.write_bytes(b"synthetic")
    digest = sha256(b"synthetic").hexdigest()
    tables: tuple[TableBackup, ...] = ()
    objects: tuple[ObjectBackup, ...] = ()
    try:
        if kind == "table":
            (bundle / "tables").mkdir()
            os.symlink(outside, bundle / "tables" / "state.copy")
            tables = (TableBackup("state", ("value",), 1, "tables/state.copy", digest),)
        elif kind == "object":
            (bundle / "objects").mkdir()
            os.symlink(outside, bundle / "objects" / "evidence.bin")
            objects = (ObjectBackup("evidence.bin", 9, digest),)
        else:
            outside_parent = tmp_path / "outside-parent"
            outside_parent.mkdir()
            (outside_parent / "evidence.bin").write_bytes(b"synthetic")
            os.symlink(outside_parent, bundle / "objects", target_is_directory=True)
            objects = (ObjectBackup("evidence.bin", 9, digest),)
    except OSError as exc:
        pytest.skip(f"Symbolic links are unavailable: {exc}")

    manifest = BackupManifest(1, "recovery", "revision", tables, objects)
    with pytest.raises(ValueError, match="symbolic link"):
        restore._verify_bundle(bundle, manifest)


def test_bundle_directory_junctions_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = tmp_path / "bundle"
    objects = bundle / "objects"
    objects.mkdir(parents=True)
    evidence = objects / "evidence.bin"
    evidence.write_bytes(b"synthetic")
    digest = sha256(b"synthetic").hexdigest()
    original = Path.is_junction
    monkeypatch.setattr(
        Path,
        "is_junction",
        lambda path: path == objects or original(path),
    )
    manifest = BackupManifest(
        1,
        "recovery",
        "revision",
        (),
        (ObjectBackup("evidence.bin", 9, digest),),
    )
    with pytest.raises(ValueError, match="symbolic link"):
        restore._verify_bundle(bundle, manifest)


def test_failed_object_cleanup_requires_target_destruction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    retained = tmp_path / "retained"
    retained.mkdir()
    cleared: list[str] = []
    monkeypatch.setattr(restore, "_remove_restore_path", lambda _path: False)
    monkeypatch.setattr(restore, "clear_restored_tables", cleared.append)

    with pytest.raises(RuntimeError, match="retained object data"):
        restore._quarantine_failed_restore(
            "target-database",
            (retained,),
            target_may_be_dirty=True,
        )
    assert cleared == ["target-database"]


def test_ambiguous_import_outcome_always_clears_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    write_manifest(
        bundle / "manifest.json",
        BackupManifest(1, "recovery", "revision", (), ()),
    )
    cleared: list[str] = []
    monkeypatch.setattr(restore, "security_authority_fence", lambda *_: nullcontext())
    monkeypatch.setattr(restore, "_upgrade_database", lambda _url: None)
    monkeypatch.setattr(restore, "_revision", lambda _url: "revision")
    monkeypatch.setattr(restore, "_restore_objects", lambda *_: None)

    def ambiguous_import(*_args: object) -> None:
        raise RuntimeError("ambiguous commit outcome")

    monkeypatch.setattr(restore, "import_tables", ambiguous_import)
    monkeypatch.setattr(restore, "_remove_restore_path", lambda _path: True)
    monkeypatch.setattr(restore, "clear_restored_tables", cleared.append)

    with pytest.raises(RuntimeError, match="ambiguous commit outcome"):
        restore.restore_backup_bundle(
            "postgresql://user@localhost/source",
            "postgresql://user@localhost/target",
            bundle,
            tmp_path / "objects",
            confirm_quiesced=True,
        )
    assert cleared == ["postgresql://user@localhost/target"]
