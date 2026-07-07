from dataclasses import replace

from coeus.core.config import Settings
from coeus.main import create_app
from coeus.services.store_semantics import (
    derive_semantic_labels,
    effective_semantic_labels,
    product_semantic_text,
    semantic_label_reasons,
)


def test_semantic_labels_are_derived_from_product_language() -> None:
    labels = derive_semantic_labels(
        "Baltic port activity",
        "Synthetic assessment brief for harbour shipping.",
    )

    assert {"assessment", "maritime"}.issubset(labels)


def test_semantic_labels_preserve_existing_and_fall_back_to_general() -> None:
    labelled = derive_semantic_labels("opaque phrase", existing=frozenset({"custom-label"}))
    fallback = derive_semantic_labels("opaque phrase")

    assert labelled == frozenset({"custom-label"})
    assert fallback == frozenset({"general-intelligence"})


def test_product_semantic_text_and_reasons_include_labels() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    product = next(
        item
        for item in app.state.store_services.repository.list_products()
        if item.metadata.title == "Regional Stability Brief"
    )

    assert "maritime" in product_semantic_text(product)
    assert "semantic-label:maritime" in semantic_label_reasons(product, "port activity")


def test_effective_semantic_labels_backfill_old_persisted_products() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    product = app.state.store_services.repository.list_products()[0]
    old_product = replace(product, metadata=replace(product.metadata, semantic_labels=frozenset()))

    assert "general-intelligence" not in effective_semantic_labels(old_product)
    assert semantic_label_reasons(old_product, "assessment brief")
