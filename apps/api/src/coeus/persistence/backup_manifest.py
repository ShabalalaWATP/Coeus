"""Checksummed manifest for coordinated logical recovery bundles."""

import json
from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path, PurePosixPath
from typing import Any


@dataclass(frozen=True)
class TableBackup:
    name: str
    columns: tuple[str, ...]
    row_count: int
    file: str
    sha256: str


@dataclass(frozen=True)
class ObjectBackup:
    key: str
    size_bytes: int
    sha256: str


@dataclass(frozen=True)
class BackupManifest:
    format_version: int
    recovery_id: str
    alembic_revision: str
    tables: tuple[TableBackup, ...]
    objects: tuple[ObjectBackup, ...]


def file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def safe_relative_path(value: str) -> Path:
    pure = PurePosixPath(value)
    if (
        pure.is_absolute()
        or not pure.parts
        or "\\" in value
        or any(_unsafe_path_component(part) for part in pure.parts)
    ):
        raise ValueError("Backup manifest contains an unsafe relative path.")
    return Path(*pure.parts)


def _unsafe_path_component(part: str) -> bool:
    if part in {"", ".", ".."} or ":" in part or any(ord(character) < 32 for character in part):
        return True
    if part.rstrip(" .") != part:
        return True
    stem = part.split(".", 1)[0].upper()
    return stem in {"CON", "PRN", "AUX", "NUL"} or stem in {
        *(f"COM{index}" for index in range(1, 10)),
        *(f"LPT{index}" for index in range(1, 10)),
    }


def write_manifest(path: Path, manifest: BackupManifest) -> None:
    path.write_text(
        json.dumps(asdict(manifest), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def read_manifest(path: Path) -> BackupManifest:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("format_version") != 1:
        raise ValueError("Unsupported backup manifest format.")
    tables = tuple(_table(item) for item in _list(payload, "tables"))
    objects = tuple(_object(item) for item in _list(payload, "objects"))
    manifest = BackupManifest(
        format_version=1,
        recovery_id=_text(payload, "recovery_id"),
        alembic_revision=_text(payload, "alembic_revision"),
        tables=tables,
        objects=objects,
    )
    paths = [table.file for table in tables] + [f"objects/{item.key}" for item in objects]
    for value in paths:
        safe_relative_path(value)
    if len(paths) != len(set(paths)):
        raise ValueError("Backup manifest contains duplicate paths.")
    return manifest


def _table(value: Any) -> TableBackup:
    if not isinstance(value, dict):
        raise ValueError("Invalid table manifest entry.")
    columns = value.get("columns")
    if not isinstance(columns, list) or not all(isinstance(item, str) for item in columns):
        raise ValueError("Invalid table manifest columns.")
    return TableBackup(
        name=_text(value, "name"),
        columns=tuple(columns),
        row_count=_integer(value, "row_count"),
        file=_text(value, "file"),
        sha256=_digest(value, "sha256"),
    )


def _object(value: Any) -> ObjectBackup:
    if not isinstance(value, dict):
        raise ValueError("Invalid object manifest entry.")
    return ObjectBackup(
        key=_text(value, "key"),
        size_bytes=_integer(value, "size_bytes"),
        sha256=_digest(value, "sha256"),
    )


def _list(payload: dict[str, Any], key: str) -> list[Any]:
    value = payload.get(key)
    if not isinstance(value, list):
        raise ValueError(f"Backup manifest {key} must be a list.")
    return value


def _text(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"Backup manifest {key} must be non-empty text.")
    return value


def _integer(payload: dict[str, Any], key: str) -> int:
    value = payload.get(key)
    if not isinstance(value, int) or value < 0:
        raise ValueError(f"Backup manifest {key} must be a non-negative integer.")
    return value


def _digest(payload: dict[str, Any], key: str) -> str:
    value = _text(payload, key)
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise ValueError(f"Backup manifest {key} must be a SHA-256 digest.")
    return value
