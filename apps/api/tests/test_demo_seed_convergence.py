"""Regression coverage for persisted baseline Store presentation updates."""

from dataclasses import replace
from pathlib import Path

from coeus.core.config import Settings
from coeus.main import create_app
from coeus.services.demo_seed import seed_demo_dataset


def test_demo_seed_converges_persisted_baseline_product_copy(tmp_path: Path) -> None:
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
    original = next(
        product for product in store.repository.list_products() if product.reference == "PROD-1003"
    )
    legacy = replace(
        original,
        metadata=replace(
            original.metadata,
            summary="MOCK DATA ONLY draft material for assessment team coordination.",
            description="Synthetic draft pack visible only to product-management users.",
            tags=original.metadata.tags | {"mock"},
        ),
    )
    store.repository.save_product(legacy)

    _seed(app)
    repaired = store.repository.get_product(original.product_id)

    assert repaired is not None
    assert repaired.metadata.summary == "Draft material for assessment team coordination."
    assert repaired.metadata.description == "Draft pack visible only to product-management users."
    assert "mock" not in repaired.metadata.tags
    assert repaired.created_at == original.created_at
    assert repaired.assets == original.assets

    repaired_timestamp = repaired.updated_at
    _seed(app)
    final = store.repository.get_product(original.product_id)
    assert final is not None
    assert final.updated_at == repaired_timestamp


def _seed(app) -> None:
    seed_demo_dataset(
        app.state.access_services.repository,
        app.state.store_services,
        app.state.object_storage,
        app.state.ticket_services,
        app.state.team_repository,
    )
