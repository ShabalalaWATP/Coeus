import json
from pathlib import Path

import pytest

from coeus.persistence.backup_manifest import (
    BackupManifest,
    ObjectBackup,
    TableBackup,
    file_sha256,
    read_manifest,
    safe_relative_path,
    write_manifest,
)


def _manifest() -> BackupManifest:
    digest = "a" * 64
    return BackupManifest(
        1,
        "recovery-1",
        "20260713_0012",
        (TableBackup("coeus_state", ("namespace",), 1, "tables/state.copy", digest),),
        (ObjectBackup("products/evidence.bin", 3, digest),),
    )


def test_manifest_round_trip_and_file_digest(tmp_path: Path) -> None:
    path = tmp_path / "manifest.json"
    write_manifest(path, _manifest())
    payload = tmp_path / "payload"
    payload.write_bytes(b"abc")

    assert read_manifest(path) == _manifest()
    assert file_sha256(payload) == (
        "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    )
    assert safe_relative_path("products/evidence.bin") == Path("products", "evidence.bin")


@pytest.mark.parametrize("value", ["", "/absolute", "../escape", "safe/../escape"])
def test_safe_relative_path_rejects_unsafe_values(value: str) -> None:
    with pytest.raises(ValueError, match="unsafe"):
        safe_relative_path(value)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("format_version", 2, "Unsupported"),
        ("tables", {}, "must be a list"),
        ("recovery_id", "", "non-empty text"),
    ],
)
def test_manifest_rejects_invalid_top_level_values(
    tmp_path: Path, field: str, value: object, message: str
) -> None:
    path = tmp_path / "manifest.json"
    write_manifest(path, _manifest())
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload[field] = value
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        read_manifest(path)


def test_manifest_rejects_duplicate_and_invalid_entries(tmp_path: Path) -> None:
    path = tmp_path / "manifest.json"
    write_manifest(path, _manifest())
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["objects"].append(payload["objects"][0])
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate"):
        read_manifest(path)

    payload["objects"] = [{"key": "object", "size_bytes": -1, "sha256": "invalid"}]
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="non-negative"):
        read_manifest(path)
