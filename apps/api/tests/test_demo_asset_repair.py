from dataclasses import replace
from hashlib import sha256
from pathlib import Path

from coeus.core.config import Settings
from coeus.main import create_app
from coeus.services.demo_asset_repair import repair_missing_local_assets


def test_missing_local_asset_is_replaced_by_an_integrity_matching_pdf(tmp_path: Path) -> None:
    app = create_app(
        Settings(
            environment="local",
            seed_demo_content=True,
            persistence_provider="memory",
            argon2_memory_cost=8_192,
            local_object_storage_path=str(tmp_path / "objects"),
        )
    )
    store = app.state.store_services
    product = next(
        product for product in store.repository.list_products() if product.reference == "PROD-1001"
    )
    product = replace(product, metadata=replace(product.metadata, tags=frozenset()))
    asset = product.assets[0]
    app.state.object_storage.delete_bytes(asset.object_key)
    binary_asset = replace(
        asset,
        name="legacy-probe.bin",
        mime_type="application/octet-stream",
        object_key=f"store/{product.product_id}/{asset.asset_id}/legacy-probe.bin",
    )
    store.repository.save_product(replace(product, assets=(binary_asset,)))

    repaired_count = repair_missing_local_assets(store, app.state.object_storage)
    repaired = store.repository.get_product(product.product_id)

    assert repaired_count == 1
    assert repaired is not None
    repaired_asset = repaired.assets[0]
    content = app.state.object_storage.read_bytes(repaired_asset.object_key)
    assert repaired_asset.name == "legacy-probe-recovered.pdf"
    assert repaired_asset.mime_type == "application/pdf"
    assert content.startswith(b"%PDF-")
    assert len(content) == repaired_asset.size_bytes
    assert sha256(content).hexdigest() == repaired_asset.sha256
