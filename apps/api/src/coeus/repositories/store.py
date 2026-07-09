from datetime import UTC, datetime
from uuid import UUID

from coeus.domain.access import AccessControlGroup, ProductStatus
from coeus.domain.store import (
    BoundingBox,
    StoreAsset,
    StoreHybridCandidate,
    StoreProduct,
    StoreProductMetadata,
    StoreSearchFilters,
    StoreVisibilityScope,
    product_in_scope,
)
from coeus.persistence.codec import decode_value, encode_value
from coeus.persistence.state_store import StateStore
from coeus.repositories.access import SeedAccessRepository, stable_seed_id
from coeus.repositories.store_hybrid import memory_hybrid_candidates
from coeus.repositories.store_projection import StoreProjection
from coeus.services.embeddings import EmbeddingService


class InMemoryStoreRepository:
    def __init__(
        self,
        access_repository: SeedAccessRepository,
        state_store: StateStore | None = None,
        projection: StoreProjection | None = None,
        embeddings: EmbeddingService | None = None,
    ) -> None:
        self._access_repository = access_repository
        self._state_store = state_store
        self._projection = projection
        self._embeddings = embeddings
        self._initialising = True
        self._products: dict[UUID, StoreProduct] = {}
        self._reference_counter = 1000
        self._seed_products()
        self._initialising = False
        self._restore_or_persist()

    def list_products(self) -> tuple[StoreProduct, ...]:
        self._refresh_from_projection(allow_empty=True)
        return tuple(sorted(self._products.values(), key=lambda product: product.metadata.title))

    def search_products(
        self, filters: StoreSearchFilters, scope: StoreVisibilityScope
    ) -> tuple[StoreProduct, ...]:
        if self._projection is None:
            return self.list_products()
        products = self._projection.search_products(filters, scope)
        self._products.update({product.product_id: product for product in products})
        return products

    def hybrid_candidates(
        self,
        filters: StoreSearchFilters,
        scope: StoreVisibilityScope,
        query: str,
        query_embedding: tuple[float, ...] | None,
        leg_limit: int = 50,
    ) -> tuple[StoreHybridCandidate, ...]:
        if self._projection is not None:
            candidates = self._projection.hybrid_candidates(
                filters,
                scope,
                query,
                query_embedding,
                leg_limit,
            )
            self._products.update(
                {candidate.product.product_id: candidate.product for candidate in candidates}
            )
            return candidates
        scoped = tuple(
            product
            for product in self.search_products(filters, scope)
            if product_in_scope(product, scope)
        )
        return memory_hybrid_candidates(
            scoped,
            query,
            query_embedding,
            self._embeddings,
            filters,
            leg_limit,
        )

    def get_visible_product(
        self, product_id: UUID, scope: StoreVisibilityScope
    ) -> StoreProduct | None:
        if self._projection is None:
            return self.get_product(product_id)
        product = self._projection.get_visible_product(product_id, scope)
        if product is not None:
            self._products[product.product_id] = product
        return product

    def get_product(self, product_id: UUID) -> StoreProduct | None:
        self._refresh_from_projection(allow_empty=True)
        return self._products.get(product_id)

    def save_product(self, product: StoreProduct) -> None:
        self._refresh_from_projection(allow_empty=True)
        self._products[product.product_id] = product
        self._persist()

    def delete_product(self, product_id: UUID) -> None:
        """Remove a product, e.g. rolling back a failed QC approval."""
        self._refresh_from_projection(allow_empty=True)
        if self._products.pop(product_id, None) is not None:
            self._persist()

    def embedded_product_count(self) -> int:
        if self._projection is None:
            return 0
        return self._projection.embedded_product_count()

    def backfill_missing_embeddings(self, batch_size: int = 500) -> int:
        if self._projection is None:
            return 0
        return self._projection.backfill_missing_embeddings(batch_size)

    def next_reference(self) -> str:
        self._refresh_from_projection(allow_empty=True)
        existing = {product.reference for product in self._products.values()}
        while True:
            self._reference_counter += 1
            reference = f"PROD-{self._reference_counter}"
            if reference not in existing:
                return reference

    def _restore_or_persist(self) -> None:
        if self._restore_from_projection():
            self._persist_json_state()
            self._persist_projection()
            return
        if self._state_store is None:
            self._persist_projection()
            return
        payload = self._state_store.load("store")
        if payload is None:
            self._persist()
            return
        products = tuple(decode_value(item) for item in payload.get("products", []))
        self._products = {product.product_id: product for product in products}
        # Never let a regressed persisted counter re-issue an existing reference.
        self._reference_counter = max(
            int(payload.get("reference_counter", 1000)),
            _max_reference_counter(products, 1000),
        )
        self._persist_projection()

    def _persist(self) -> None:
        if self._initialising:
            return
        self._persist_json_state()
        self._persist_projection()

    def _persist_json_state(self) -> None:
        if self._state_store is None:
            return
        products = sorted(self._products.values(), key=lambda product: product.metadata.title)
        self._state_store.save(
            "store",
            {
                "reference_counter": self._reference_counter,
                "products": [encode_value(product) for product in products],
            },
        )

    def _persist_projection(self) -> None:
        if self._projection is None:
            return
        products = tuple(
            sorted(self._products.values(), key=lambda product: product.metadata.title)
        )
        self._projection.save_products(products)

    def _restore_from_projection(self) -> bool:
        return self._refresh_from_projection(allow_empty=False)

    def _refresh_from_projection(self, *, allow_empty: bool) -> bool:
        if self._projection is None:
            return False
        products = self._projection.list_products()
        if not products and not allow_empty:
            return False
        self._products = {product.product_id: product for product in products}
        self._reference_counter = _max_reference_counter(products, self._reference_counter)
        return True

    def _seed_products(self) -> None:
        regional = self._acg_by_code("ACG-ALPHA-REGIONAL")
        collection = self._acg_by_code("ACG-BRAVO-COLLECTION")
        assessment = self._acg_by_code("ACG-CHARLIE-ASSESSMENT")
        admin = self._access_repository.get_user_by_username("admin@example.test")
        if admin is None:
            raise RuntimeError("Missing required seed user admin@example.test.")
        now = datetime.now(UTC)
        products = (
            self._seed_product(
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
                project_id=None,
                status=ProductStatus.PUBLISHED,
                created_by_user_id=admin.user_id,
                created_at=now,
            ),
            self._seed_product(
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
                project_id=None,
                status=ProductStatus.PUBLISHED,
                created_by_user_id=admin.user_id,
                created_at=now,
            ),
            self._seed_product(
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
                project_id=None,
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
        semantic_labels: frozenset[str],
        acg_ids: frozenset[UUID],
        project_id: UUID | None,
        status: ProductStatus,
        created_by_user_id: UUID,
        created_at: datetime,
        time_period: tuple[str, str] | None = None,
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
                semantic_labels=semantic_labels,
                acg_ids=acg_ids,
                project_id=project_id,
                status=status,
                time_period_start=time_period[0] if time_period else None,
                time_period_end=time_period[1] if time_period else None,
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


def _max_reference_counter(products: tuple[StoreProduct, ...], default: int) -> int:
    counter = default
    for product in products:
        prefix, _, suffix = product.reference.partition("-")
        if prefix == "PROD" and suffix.isdigit():
            counter = max(counter, int(suffix))
    return counter
