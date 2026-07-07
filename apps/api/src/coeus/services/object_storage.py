from pathlib import Path

from coeus.domain.store import StoreProduct, object_key_segment


class LocalObjectStorage:
    def __init__(self, root: str | Path) -> None:
        self._root = Path(root)

    def write_bytes(self, object_key: str, content: bytes) -> None:
        path = self.path_for(object_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    def exists(self, object_key: str) -> bool:
        return self.path_for(object_key).is_file()

    def path_for(self, object_key: str) -> Path:
        parts = _safe_parts(object_key)
        root = self._root.resolve()
        path = root.joinpath(*parts).resolve()
        if not path.is_relative_to(root):
            raise ValueError("Object key escapes local storage root.")
        return path


def seed_store_asset_placeholders(
    storage: LocalObjectStorage,
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


def _safe_parts(object_key: str) -> tuple[str, ...]:
    parts = tuple(part for part in object_key.replace("\\", "/").split("/") if part)
    if not parts or any(part in {".", ".."} for part in parts):
        raise ValueError("Object key contains an unsafe path segment.")
    return tuple(object_key_segment(part) for part in parts)
