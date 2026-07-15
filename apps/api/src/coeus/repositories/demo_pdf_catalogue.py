"""Build deterministic Store products and genuine PDF object bytes."""

from dataclasses import replace
from datetime import UTC, datetime
from functools import lru_cache
from hashlib import sha256
from uuid import UUID

from coeus.domain.access import ProductStatus
from coeus.domain.store import StoreAsset, StoreProduct, StoreProductMetadata
from coeus.repositories.access import stable_seed_id
from coeus.repositories.demo_pdf import build_demo_pdf_bytes
from coeus.repositories.demo_pdf_specs import DemoPdfSeed, demo_pdf_seeds

_CREATED_AT = datetime(2026, 7, 1, tzinfo=UTC)


def build_pdf_corpus(
    acg_ids: dict[str, UUID], created_by: UUID
) -> tuple[tuple[StoreProduct, ...], tuple[tuple[str, bytes], ...], frozenset[str]]:
    return _build_pdf_corpus_cached(tuple(sorted(acg_ids.items())), created_by)


@lru_cache(maxsize=4)
def _build_pdf_corpus_cached(
    acg_items: tuple[tuple[str, UUID], ...], created_by: UUID
) -> tuple[tuple[StoreProduct, ...], tuple[tuple[str, bytes], ...], frozenset[str]]:
    acg_ids = dict(acg_items)
    products: list[StoreProduct] = []
    objects: list[tuple[str, bytes]] = []
    used_codes: set[str] = set()
    for seed in demo_pdf_seeds():
        acg_id = acg_ids.get(seed.acg_code)
        if acg_id is None:
            continue
        product = _build_product(seed, acg_id, created_by)
        content = build_demo_pdf_bytes(product)
        asset = replace(
            product.assets[0], size_bytes=len(content), sha256=sha256(content).hexdigest()
        )
        product = replace(product, assets=(asset,))
        products.append(product)
        objects.append((asset.object_key, content))
        used_codes.add(seed.acg_code)
    return tuple(products), tuple(objects), frozenset(used_codes)


def _build_product(seed: DemoPdfSeed, acg_id: UUID, created_by: UUID) -> StoreProduct:
    product_id = stable_seed_id(f"store-{seed.seed_name}")
    asset_id = stable_seed_id(f"store-asset-{seed.seed_name}-pdf")
    filename = f"{seed.seed_name}.pdf"
    asset = StoreAsset(
        asset_id=asset_id,
        name=filename,
        asset_type="pdf",
        mime_type="application/pdf",
        size_bytes=0,
        sha256="0" * 64,
        object_key=f"store/{product_id}/{asset_id}/{filename}",
        preview_kind="pdf_metadata",
    )
    return StoreProduct(
        product_id=product_id,
        reference=seed.reference,
        metadata=StoreProductMetadata(
            title=seed.title,
            summary=seed.summary,
            description=seed.description,
            product_type=seed.product_type,
            source_type=seed.source_type,
            owner_team=seed.owner_team,
            area_or_region=seed.area_or_region,
            classification_level=seed.classification_level,
            releasability=frozenset({"MOCK"}),
            handling_caveats=frozenset({"MOCK DATA ONLY"}),
            tags=seed.tags,
            semantic_labels=seed.semantic_labels,
            acg_ids=frozenset({acg_id}),
            status=ProductStatus.PUBLISHED,
            time_period_start=seed.time_period[0],
            time_period_end=seed.time_period[1],
            geojson_ref=None,
            bounding_box=None,
        ),
        assets=(asset,),
        created_by_user_id=created_by,
        created_at=_CREATED_AT,
        updated_at=_CREATED_AT,
    )
