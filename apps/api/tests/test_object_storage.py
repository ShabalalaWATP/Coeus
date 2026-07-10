from pathlib import Path

import pytest

from coeus.core.config import Settings
from coeus.services.object_storage import LocalObjectStorage, build_object_storage


def test_local_object_storage_reads_deletes_and_rejects_unsafe_keys(tmp_path: Path) -> None:
    storage = LocalObjectStorage(tmp_path)
    storage.write_bytes("top-level.bin", b"content")

    assert storage.read_bytes("top-level.bin") == b"content"
    storage.delete_bytes("top-level.bin")
    assert not storage.exists("top-level.bin")

    for unsafe_key in ("", "../escape.bin", "folder/./item.bin"):
        with pytest.raises(ValueError, match="unsafe path segment"):
            storage.path_for(unsafe_key)


def test_object_storage_factory_fails_closed_for_future_gcs_provider() -> None:
    settings = Settings(environment="test", object_storage_provider="gcs")

    with pytest.raises(ValueError, match="GCS remains a future migration path"):
        build_object_storage(settings)


def test_local_object_storage_removes_partial_temporary_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    storage = LocalObjectStorage(tmp_path)
    original_write = Path.write_bytes

    def write_then_fail(path: Path, _content: bytes) -> int:
        original_write(path, b"partial")
        raise OSError("synthetic disk failure")

    monkeypatch.setattr(Path, "write_bytes", write_then_fail)

    with pytest.raises(OSError, match="synthetic disk failure"):
        storage.write_bytes("nested/asset.bin", b"complete")

    assert not storage.exists("nested/asset.bin")
    assert list(tmp_path.rglob("*")) == [tmp_path / "nested"]
