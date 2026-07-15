"""Rich local demo store catalogue (MOCK DATA ONLY).

Deterministic products spread across the themed need-to-know ACGs, covering
every canonical product type (standardised reports, summaries, satellite
imagery, geospatial overlays, database extracts, SIGINT datasets, product
bundles and fused outputs) with type-appropriate assets, metadata and tags.
Test environments do not load this; see ``Settings.should_seed_demo``. Product
and asset IDs and references are stable, so re-seeding never duplicates.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from coeus.domain.access import ProductStatus
from coeus.domain.store import BoundingBox, StoreAsset, StoreProduct, StoreProductMetadata
from coeus.repositories.access import AccessRepository, stable_seed_id
from coeus.repositories.demo_catalogue_data import (
    ASSET_KINDS,
    BOUNDING_BOX,
    DEMO_REFERENCE_BASE,
    DISCIPLINE_META,
    GEOJSON_KINDS,
    REGION_AREAS,
    TYPE_LABELS,
)
from coeus.repositories.demo_catalogue_specs import BASE_SPECS, SHOWCASE_SPECS
from coeus.repositories.demo_pdf_catalogue import build_pdf_corpus

_BOUNDING_BOX = BoundingBox(*BOUNDING_BOX)


@dataclass(frozen=True)
class ProductSpec:
    acg_code: str
    title: str
    product_type: str
    asset_kind: str
    classification: int
    status: ProductStatus
    period: tuple[str, str]
    tags: frozenset[str]
    labels: frozenset[str]


@dataclass(frozen=True)
class DemoCatalogue:
    products: tuple[StoreProduct, ...]
    acg_codes: frozenset[str]
    generated_assets: tuple[tuple[str, bytes], ...] = ()


def build_demo_catalogue(access_repository: AccessRepository) -> DemoCatalogue:
    admin = access_repository.get_user_by_username("admin@example.test")
    if admin is None:
        raise RuntimeError("Missing required seed user admin@example.test.")
    acg_ids = {acg.code: acg.acg_id for acg in access_repository.list_acgs()}
    now = datetime.now(UTC)
    products: list[StoreProduct] = []
    used_codes: set[str] = set()
    for index, spec in enumerate(_normalised_specs()):
        acg_id = acg_ids.get(spec.acg_code)
        if acg_id is None:
            continue
        used_codes.add(spec.acg_code)
        products.append(_build_product(spec, index, acg_id, admin.user_id, now))
    pdf_products, generated_assets, pdf_codes = build_pdf_corpus(acg_ids, admin.user_id)
    products.extend(pdf_products)
    used_codes.update(pdf_codes)
    return DemoCatalogue(tuple(products), frozenset(used_codes), generated_assets)


def _normalised_specs() -> list[ProductSpec]:
    specs: list[ProductSpec] = []
    for code, title, classification, status, period in BASE_SPECS:
        _, region_code, discipline = code.split("-")
        product_type, asset_kind, tags, labels = DISCIPLINE_META[discipline]
        area = REGION_AREAS[region_code]
        specs.append(
            ProductSpec(
                acg_code=code,
                title=title,
                product_type=product_type,
                asset_kind=asset_kind,
                classification=classification,
                status=status,
                period=period,
                tags=frozenset({*tags, region_code.lower()}),
                labels=frozenset({*labels, _area_label(area)}),
            )
        )
    for (
        code,
        title,
        product_type,
        asset_kind,
        classification,
        status,
        period,
        tags,
    ) in SHOWCASE_SPECS:
        _, region_code, discipline = code.split("-")
        area = REGION_AREAS[region_code]
        specs.append(
            ProductSpec(
                acg_code=code,
                title=title,
                product_type=product_type,
                asset_kind=asset_kind,
                classification=classification,
                status=status,
                period=period,
                tags=frozenset({*tags, region_code.lower(), discipline.lower()}),
                labels=frozenset({*TYPE_LABELS.get(product_type, ()), _area_label(area)}),
            )
        )
    return specs


def _area_label(area: str) -> str:
    return area.split(",")[0].strip().lower()


def _build_product(
    spec: ProductSpec, index: int, acg_id: UUID, created_by: UUID, created_at: datetime
) -> StoreProduct:
    _, region_code, discipline = spec.acg_code.split("-")
    area = REGION_AREAS[region_code]
    seed_name = f"demo-{index:03d}-{spec.acg_code.lower()}"
    product_id = stable_seed_id(f"store-{seed_name}")
    reference = f"PROD-{DEMO_REFERENCE_BASE + index + 1}"
    geojson_ref = f"mock://geojson/{seed_name}" if spec.asset_kind in GEOJSON_KINDS else None
    type_label = spec.product_type.replace("_", " ")
    return StoreProduct(
        product_id=product_id,
        reference=reference,
        metadata=StoreProductMetadata(
            title=spec.title,
            summary=f"MOCK DATA ONLY {type_label} covering {area}.",
            description=(
                f"Synthetic {type_label} for {area} ({discipline} reporting). "
                "MOCK DATA ONLY, generated for the local demo dataset."
            ),
            product_type=spec.product_type,
            source_type=_SOURCE_TYPES.get(discipline, "finished_assessment"),
            owner_team="Collection" if discipline in {"SIGINT", "GEOINT"} else "RFA",
            area_or_region=area,
            classification_level=spec.classification,
            releasability=frozenset({"MOCK"}),
            handling_caveats=frozenset({"MOCK DATA ONLY"}),
            tags=spec.tags,
            semantic_labels=spec.labels,
            acg_ids=frozenset({acg_id}),
            status=spec.status,
            time_period_start=spec.period[0],
            time_period_end=spec.period[1],
            geojson_ref=geojson_ref,
            bounding_box=_BOUNDING_BOX,
        ),
        assets=_build_assets(seed_name, spec.asset_kind, product_id),
        created_by_user_id=created_by,
        created_at=created_at,
        updated_at=created_at,
    )


def _build_assets(seed_name: str, asset_kind: str, product_id: UUID) -> tuple[StoreAsset, ...]:
    assets: list[StoreAsset] = []
    for suffix, asset_type, mime_type, preview_kind, size_bytes in ASSET_KINDS[asset_kind]:
        asset_id = stable_seed_id(f"store-asset-{seed_name}-{suffix}")
        name = f"{seed_name}-{suffix}"
        assets.append(
            StoreAsset(
                asset_id=asset_id,
                name=name,
                asset_type=asset_type,
                mime_type=mime_type,
                size_bytes=size_bytes,
                sha256="c" * 64,
                object_key=f"store/{product_id}/{asset_id}/{name}",
                preview_kind=preview_kind,
            )
        )
    return tuple(assets)


_SOURCE_TYPES = {
    "CYBER": "finished_assessment",
    "HUMINT": "finished_assessment",
    "SIGINT": "sensor",
    "GEOINT": "sensor",
    "OSINT": "finished_assessment",
}
