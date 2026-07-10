from pathlib import Path
from typing import Protocol, runtime_checkable
from uuid import uuid4

from coeus.core.config import Settings
from coeus.domain.store import StoreProduct, object_key_segment


@runtime_checkable
class ObjectStorage(Protocol):
    def write_bytes(self, object_key: str, content: bytes) -> None:
        pass

    def read_bytes(self, object_key: str) -> bytes:
        pass

    def exists(self, object_key: str) -> bool:
        pass

    def delete_bytes(self, object_key: str) -> None:
        pass


class LocalObjectStorage:
    def __init__(self, root: str | Path) -> None:
        self._root = Path(root)

    def write_bytes(self, object_key: str, content: bytes) -> None:
        path = self.path_for(object_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
        try:
            temporary.write_bytes(content)
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)

    def exists(self, object_key: str) -> bool:
        return self.path_for(object_key).is_file()

    def read_bytes(self, object_key: str) -> bytes:
        return self.path_for(object_key).read_bytes()

    def delete_bytes(self, object_key: str) -> None:
        path = self.path_for(object_key)
        path.unlink(missing_ok=True)
        self._remove_empty_parents(path.parent)

    def path_for(self, object_key: str) -> Path:
        parts = _safe_parts(object_key)
        root = self._root.resolve()
        path = root.joinpath(*parts).resolve()
        if not path.is_relative_to(root):
            raise ValueError("Object key escapes local storage root.")
        return path

    def _remove_empty_parents(self, start: Path) -> None:
        root = self._root.resolve()
        current = start.resolve()
        while current != root and current.is_relative_to(root):
            try:
                current.rmdir()
            except OSError:
                return
            current = current.parent


def seed_store_asset_placeholders(
    storage: ObjectStorage,
    products: tuple[StoreProduct, ...],
) -> None:
    for product in products:
        for asset in product.assets:
            if storage.exists(asset.object_key):
                continue
            content = (
                f"MOCK DATA ONLY\n{product.reference}\n{product.metadata.title}\n{asset.name}\n"
            ).encode()
            storage.write_bytes(asset.object_key, content)


def build_object_storage(settings: Settings) -> ObjectStorage:
    if settings.object_storage_provider != "local":
        raise ValueError(
            "Only local object storage is implemented. GCS remains a future migration path."
        )
    return LocalObjectStorage(settings.local_object_storage_path)


def _safe_parts(object_key: str) -> tuple[str, ...]:
    parts = tuple(part for part in object_key.replace("\\", "/").split("/") if part)
    if not parts or any(part in {".", ".."} for part in parts):
        raise ValueError("Object key contains an unsafe path segment.")
    return tuple(object_key_segment(part) for part in parts)
