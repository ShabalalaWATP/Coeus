from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from coeus.domain.access import AccessControlGroup, ProductStatus
from coeus.domain.store import BoundingBox, StoreAsset, StoreProduct, StoreProductMetadata
from coeus.repositories.access import SeedAccessRepository, stable_seed_id

STORE_SEED_REFERENCE_COUNTER = 1003


@dataclass(frozen=True)
class SeedProductInput:
    seed_name: str
    reference: str
    title: str
    summary: str
    description: str
    product_type: str
    source_type: str
    owner_team: str
    area_or_region: str
    classification_level: int
    tags: frozenset[str]
    semantic_labels: frozenset[str]
    acg_ids: frozenset[UUID]
    status: ProductStatus
    time_period: tuple[str, str] | None = None


def seed_store_products(access_repository: SeedAccessRepository) -> tuple[StoreProduct, ...]:
    regional = _acg_by_code(access_repository, "ACG-ALPHA-REGIONAL")
    collection = _acg_by_code(access_repository, "ACG-BRAVO-COLLECTION")
    assessment = _acg_by_code(access_repository, "ACG-CHARLIE-ASSESSMENT")
    admin = access_repository.get_user_by_username("admin@example.test")
    if admin is None:
        raise RuntimeError("Missing required seed user admin@example.test.")
    now = datetime.now(UTC)
    return tuple(
        _seed_product(seed, created_by_user_id=admin.user_id, created_at=now)
        for seed in (
            SeedProductInput(
                seed_name="regional-stability-brief",
                time_period=("2026-03-01", "2026-04-30"),
                reference="PROD-1001",
                title="Regional Stability Brief",
                summary="MOCK DATA ONLY assessment summary for Baltic regional stability.",
                description="Synthetic customer-facing assessment linked to Alpha Regional.",
                product_type="assessment_report",
                source_type="finished_assessment",
                owner_team="RFA",
                area_or_region="Baltic ports",
                classification_level=2,
                tags=frozenset({"regional", "ports", "baltic"}),
                semantic_labels=frozenset({"assessment", "maritime"}),
                acg_ids=frozenset({regional.acg_id}),
                status=ProductStatus.PUBLISHED,
            ),
            SeedProductInput(
                seed_name="collection-sensor-summary",
                time_period=("2026-05-01", "2026-06-15"),
                reference="PROD-1002",
                title="Collection Sensor Summary",
                summary="MOCK DATA ONLY sensor summary for collection team members.",
                description="Synthetic collection product protected by Bravo Collection.",
                product_type="sigint_mock",
                source_type="sensor",
                owner_team="Collection",
                area_or_region="North Sea",
                classification_level=3,
                tags=frozenset({"collection", "sensor", "mock"}),
                semantic_labels=frozenset({"collection", "sigint"}),
                acg_ids=frozenset({collection.acg_id}),
                status=ProductStatus.PUBLISHED,
            ),
            SeedProductInput(
                seed_name="assessment-draft-pack",
                time_period=("2026-06-01", "2026-06-30"),
                reference="PROD-1003",
                title="Assessment Draft Pack",
                summary="MOCK DATA ONLY draft material for assessment team coordination.",
                description="Synthetic draft pack visible only to product-management users.",
                product_type="finished_output",
                source_type="working_draft",
                owner_team="RFA",
                area_or_region="Baltic ports",
                classification_level=3,
                tags=frozenset({"draft", "assessment", "mock"}),
                semantic_labels=frozenset({"assessment"}),
                acg_ids=frozenset({assessment.acg_id}),
                status=ProductStatus.DRAFT,
            ),
        )
    )


def _seed_product(
    seed: SeedProductInput, *, created_by_user_id: UUID, created_at: datetime
) -> StoreProduct:
    product_id = stable_seed_id(f"store-product-{seed.seed_name}")
    asset = _seed_asset(seed.seed_name, product_id)
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
            acg_ids=seed.acg_ids,
            status=seed.status,
            time_period_start=seed.time_period[0] if seed.time_period else None,
            time_period_end=seed.time_period[1] if seed.time_period else None,
            geojson_ref=None,
            bounding_box=BoundingBox(-7.0, 54.0, 31.0, 66.0),
        ),
        assets=(asset,),
        created_by_user_id=created_by_user_id,
        created_at=created_at,
        updated_at=created_at,
    )


def _seed_asset(seed_name: str, product_id: UUID) -> StoreAsset:
    asset_id = stable_seed_id(f"store-asset-{seed_name}")
    name = f"{seed_name}.pdf"
    return StoreAsset(
        asset_id=asset_id,
        name=name,
        asset_type="pdf",
        mime_type="application/pdf",
        size_bytes=12_000,
        sha256="b" * 64,
        object_key=f"store/{product_id}/{asset_id}/{name}",
        preview_kind="pdf_metadata",
    )


def _acg_by_code(access_repository: SeedAccessRepository, code: str) -> AccessControlGroup:
    for acg in access_repository.list_acgs():
        if acg.code == code:
            return acg
    raise RuntimeError(f"Missing required seed ACG {code}.")
