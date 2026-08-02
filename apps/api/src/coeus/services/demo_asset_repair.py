"""Materialise and repair deterministic local exercise assets."""

from dataclasses import replace
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import PurePosixPath

from coeus.domain.store import StoreAsset, StoreProduct
from coeus.repositories.demo_asset_content import build_demo_asset_bytes
from coeus.repositories.demo_pdf import build_demo_pdf_bytes
from coeus.services.object_storage import ObjectStorage
from coeus.services.store import StoreServices


def materialise_demo_products(
    products: tuple[StoreProduct, ...],
) -> tuple[tuple[StoreProduct, ...], tuple[tuple[str, bytes], ...]]:
    materialised_products: list[StoreProduct] = []
    objects: list[tuple[str, bytes]] = []
    for product in products:
        assets: list[StoreAsset] = []
        for asset in product.assets:
            content = build_demo_asset_bytes(product, asset)
            updated = _with_content(asset, content)
            assets.append(updated)
            objects.append((updated.object_key, content))
        materialised_products.append(replace(product, assets=tuple(assets)))
    return tuple(materialised_products), tuple(objects)


def repair_missing_local_assets(store: StoreServices, object_storage: ObjectStorage) -> int:
    """Replace missing local exercise objects with deterministic recovery PDFs."""

    repaired_count = 0
    for product in store.repository.list_products():
        changed = False
        repaired_assets: list[StoreAsset] = []
        for asset in product.assets:
            if object_storage.exists(asset.object_key):
                repaired_assets.append(asset)
                continue
            content = build_demo_pdf_bytes(product)
            repaired = _recovery_pdf_asset(asset, content)
            object_storage.write_bytes(repaired.object_key, content)
            repaired_assets.append(repaired)
            repaired_count += 1
            changed = True
        if changed:
            store.repository.save_product(
                replace(product, assets=tuple(repaired_assets), updated_at=datetime.now(UTC))
            )
    return repaired_count


def _with_content(asset: StoreAsset, content: bytes) -> StoreAsset:
    return replace(asset, size_bytes=len(content), sha256=sha256(content).hexdigest())


def _recovery_pdf_asset(asset: StoreAsset, content: bytes) -> StoreAsset:
    if asset.mime_type == "application/pdf":
        return _with_content(asset, content)
    path = PurePosixPath(asset.object_key)
    name = f"{PurePosixPath(asset.name).stem}-recovered.pdf"
    return replace(
        _with_content(asset, content),
        name=name,
        asset_type="pdf",
        mime_type="application/pdf",
        object_key=str(path.parent / name),
        preview_kind="pdf_metadata",
    )
