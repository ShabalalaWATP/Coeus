from datetime import UTC, datetime
from uuid import UUID, uuid4

from coeus.domain.access import AccessControlGroup, ProductStatus
from coeus.domain.store import BoundingBox, StoreAsset, StoreProduct, StoreProductMetadata
from coeus.repositories.access import SeedAccessRepository, stable_seed_id


class InMemoryStoreRepository:
    def __init__(self, access_repository: SeedAccessRepository) -> None:
        self._access_repository = access_repository
        self._products: dict[UUID, StoreProduct] = {}
        self._reference_counter = 1000
        self._seed_products()

    def list_products(self) -> tuple[StoreProduct, ...]:
        return tuple(sorted(self._products.values(), key=lambda product: product.metadata.title))

    def get_product(self, product_id: UUID) -> StoreProduct | None:
        return self._products.get(product_id)

    def save_product(self, product: StoreProduct) -> None:
        self._products[product.product_id] = product

    def next_reference(self) -> str:
        self._reference_counter += 1
        return f"PROD-{self._reference_counter}"

    def _seed_products(self) -> None:
        regional = self._acg_by_code("ACG-ALPHA-REGIONAL")
        collection = self._acg_by_code("ACG-BRAVO-COLLECTION")
        assessment = self._acg_by_code("ACG-CHARLIE-ASSESSMENT")
        project = self._access_repository.list_projects()[0]
        admin = self._access_repository.get_user_by_username("admin@example.test")
        if admin is None:
            raise RuntimeError("Missing required seed user admin@example.test.")
        now = datetime.now(UTC)
        products = (
            self._seed_product(
                seed_name="regional-stability-brief",
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
                acg_ids=frozenset({regional.acg_id}),
                project_id=project.project_id,
                status=ProductStatus.PUBLISHED,
                created_by_user_id=admin.user_id,
                created_at=now,
            ),
            self._seed_product(
                seed_name="collection-sensor-summary",
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
                acg_ids=frozenset({collection.acg_id}),
                project_id=project.project_id,
                status=ProductStatus.PUBLISHED,
                created_by_user_id=admin.user_id,
                created_at=now,
            ),
            self._seed_product(
                seed_name="assessment-draft-pack",
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
                acg_ids=frozenset({assessment.acg_id}),
                project_id=project.project_id,
                status=ProductStatus.DRAFT,
                created_by_user_id=admin.user_id,
                created_at=now,
            ),
        )
        self._products = {product.product_id: product for product in products}
        self._reference_counter = 1003

    def _seed_product(
        self,
        *,
        seed_name: str,
        reference: str,
        title: str,
        summary: str,
        description: str,
        product_type: str,
        source_type: str,
        owner_team: str,
        area_or_region: str,
        classification_level: int,
        tags: frozenset[str],
        acg_ids: frozenset[UUID],
        project_id: UUID,
        status: ProductStatus,
        created_by_user_id: UUID,
        created_at: datetime,
    ) -> StoreProduct:
        product_id = stable_seed_id(f"store-product-{seed_name}")
        asset = self._seed_asset(seed_name, product_id)
        return StoreProduct(
            product_id=product_id,
            reference=reference,
            metadata=StoreProductMetadata(
                title=title,
                summary=summary,
                description=description,
                product_type=product_type,
                source_type=source_type,
                owner_team=owner_team,
                area_or_region=area_or_region,
                classification_level=classification_level,
                releasability=frozenset({"MOCK"}),
                handling_caveats=frozenset({"MOCK DATA ONLY"}),
                tags=tags,
                acg_ids=acg_ids,
                project_id=project_id,
                status=status,
                time_period_start=None,
                time_period_end=None,
                geojson_ref=None,
                bounding_box=BoundingBox(-7.0, 54.0, 31.0, 66.0),
            ),
            assets=(asset,),
            created_by_user_id=created_by_user_id,
            created_at=created_at,
            updated_at=created_at,
        )

    @staticmethod
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

    def _acg_by_code(self, code: str) -> AccessControlGroup:
        for acg in self._access_repository.list_acgs():
            if acg.code == code:
                return acg
        raise RuntimeError(f"Missing required seed ACG {code}.")


def new_store_product_id() -> UUID:
    return uuid4()
