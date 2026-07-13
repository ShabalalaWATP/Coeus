from dataclasses import dataclass, field
from datetime import UTC, datetime
from re import fullmatch
from uuid import UUID

from coeus.core.errors import AppError
from coeus.core.permissions import Permission
from coeus.core.resource_limits import (
    MAX_PRODUCT_ASSET_METADATA_BYTES,
    MAX_PRODUCT_ASSETS,
    text_bytes,
)
from coeus.domain.access import ProductStatus
from coeus.domain.auth import UserAccount
from coeus.domain.store import (
    BoundingBox,
    StoreAsset,
    StoreFacets,
    StoreHybridCandidate,
    StoreProduct,
    StoreProductMetadata,
    StoreSearchFilters,
    StoreSearchResult,
    object_key_segment,
)
from coeus.domain.store_filters import structured_filter_match
from coeus.repositories.access import AccessRepository
from coeus.repositories.store import StoreRepository
from coeus.repositories.store_ids import new_store_product_id
from coeus.services.audit import AuditLog
from coeus.services.embeddings import EmbeddingService
from coeus.services.store_access import StoreAssetService, StoreDetailService
from coeus.services.store_metadata_suggestions import MetadataSuggestionService
from coeus.services.store_owner_policy import normalise_owner_team, require_owner_permission
from coeus.services.store_product_policy import StoreProductAccessPolicy
from coeus.services.store_search_results import (
    exact_text_hit,
    facets_for,
    has_text_query,
    hybrid_hits,
    paged_result,
    projected_page_result,
    sort_hits_by_relevance,
    without_text_query,
)
from coeus.services.store_semantics import derive_semantic_labels

HASH_PATTERN = r"[a-fA-F0-9]{64}"
STORE_BROWSE_HYBRID_LEG_LIMIT = 500


@dataclass(frozen=True)
class StoreProductDraft:
    title: str
    summary: str
    description: str
    product_type: str
    source_type: str
    owner_team: str
    area_or_region: str
    classification_level: int
    releasability: frozenset[str]
    handling_caveats: frozenset[str]
    tags: frozenset[str]
    acg_ids: frozenset[UUID]
    status: ProductStatus
    time_period_start: str | None
    time_period_end: str | None
    geojson_ref: str | None
    bounding_box: BoundingBox | None
    assets: tuple[StoreAsset, ...]
    semantic_labels: frozenset[str] = field(default_factory=frozenset)


class StoreIngestionService:
    def __init__(
        self,
        repository: StoreRepository,
        access_repository: AccessRepository,
        audit_log: AuditLog,
    ) -> None:
        self._repository = repository
        self._access_repository = access_repository
        self._audit_log = audit_log

    def create_existing_product(
        self,
        actor: UserAccount,
        draft: StoreProductDraft,
        *,
        audit: bool = True,
    ) -> StoreProduct:
        self._require(actor, Permission.PRODUCT_CREATE_EXISTING)
        owner_team = normalise_owner_team(draft.owner_team)
        require_owner_permission(actor, owner_team)
        self._validate_acgs(actor, draft.acg_ids)
        self._validate_assets(draft.assets)
        if draft.product_type == "geographic_product" and not (
            draft.geojson_ref or draft.bounding_box
        ):
            raise AppError(
                409, "geographic_metadata_required", "Geographic products need geometry."
            )
        assets = self._with_object_keys(draft.assets)
        semantic_labels = derive_semantic_labels(
            draft.title,
            draft.summary,
            draft.description,
            draft.product_type,
            draft.source_type,
            draft.owner_team,
            draft.area_or_region,
            " ".join(draft.tags),
            " ".join(asset.asset_type for asset in assets),
            existing=draft.semantic_labels,
        )
        now = datetime.now(UTC)
        product = StoreProduct(
            product_id=new_store_product_id(),
            reference=self._repository.next_reference(),
            metadata=StoreProductMetadata(
                title=draft.title,
                summary=draft.summary,
                description=draft.description,
                product_type=draft.product_type,
                source_type=draft.source_type,
                owner_team=owner_team,
                area_or_region=draft.area_or_region,
                classification_level=draft.classification_level,
                releasability=draft.releasability,
                handling_caveats=draft.handling_caveats,
                tags=draft.tags,
                acg_ids=draft.acg_ids,
                status=draft.status,
                time_period_start=draft.time_period_start,
                time_period_end=draft.time_period_end,
                geojson_ref=draft.geojson_ref,
                bounding_box=draft.bounding_box,
                semantic_labels=semantic_labels,
            ),
            assets=assets,
            created_by_user_id=actor.user_id,
            created_at=now,
            updated_at=now,
        )
        self._repository.save_product(product)
        if audit:
            try:
                self.audit_product_created(actor, product)
            except Exception:
                self._repository.delete_product(product.product_id)
                raise
        return product

    def audit_product_created(self, actor: UserAccount, product: StoreProduct) -> None:
        self._audit_log.record(
            "product_created",
            str(actor.user_id),
            {"product_id": str(product.product_id), "reference": product.reference},
        )

    def _validate_acgs(self, actor: UserAccount, acg_ids: frozenset[UUID]) -> None:
        if not acg_ids:
            raise AppError(409, "product_acg_required", "Products must have at least one ACG.")
        actor_acgs = self._access_repository.active_acg_ids_for_user(actor.user_id)
        for acg_id in acg_ids:
            acg = self._access_repository.get_acg(acg_id)
            if acg is None or not acg.is_active:
                raise AppError(409, "product_acg_required", "Products must use active ACGs.")
            if (
                Permission.PRODUCT_READ_RESTRICTED not in actor.permissions
                and Permission.ACG_ASSIGN_PRODUCT not in actor.permissions
                and acg_id not in actor_acgs
            ):
                raise AppError(403, "acg_not_authorised", "User cannot assign that ACG.")

    @staticmethod
    def _require(actor: UserAccount, permission: Permission) -> None:
        if permission not in actor.permissions:
            raise AppError(403, "forbidden", "Permission denied.")

    @staticmethod
    def _validate_assets(assets: tuple[StoreAsset, ...]) -> None:
        if not assets:
            raise AppError(409, "asset_required", "Products must include at least one asset.")
        metadata_bytes = sum(
            text_bytes(asset.name, asset.asset_type, asset.mime_type, asset.sha256)
            for asset in assets
        )
        if len(assets) > MAX_PRODUCT_ASSETS or metadata_bytes > MAX_PRODUCT_ASSET_METADATA_BYTES:
            raise AppError(409, "asset_limit_reached", "Product asset metadata exceeds its limit.")
        for asset in assets:
            if not fullmatch(HASH_PATTERN, asset.sha256):
                raise AppError(409, "asset_hash_invalid", "Asset SHA-256 must be 64 hex chars.")
            if asset.size_bytes < 1:
                raise AppError(409, "asset_size_invalid", "Asset size must be positive.")

    @staticmethod
    def _with_object_keys(assets: tuple[StoreAsset, ...]) -> tuple[StoreAsset, ...]:
        return tuple(
            StoreAsset(
                asset_id=asset.asset_id,
                name=asset.name,
                asset_type=asset.asset_type,
                mime_type=asset.mime_type,
                size_bytes=asset.size_bytes,
                sha256=asset.sha256,
                object_key=f"store/uploads/{asset.asset_id}/{object_key_segment(asset.name)}",
                preview_kind=asset.preview_kind,
            )
            for asset in assets
        )


class StoreSearchService:
    def __init__(
        self,
        repository: StoreRepository,
        policy: StoreProductAccessPolicy,
        embeddings: EmbeddingService | None = None,
    ) -> None:
        self._repository = repository
        self._policy = policy
        self._embeddings = embeddings

    def search(self, actor: UserAccount, filters: StoreSearchFilters) -> StoreSearchResult:
        if Permission.PRODUCT_SEARCH not in actor.permissions:
            raise AppError(403, "forbidden", "Permission denied.")
        # Need-to-know: the store never lists a user's whole visible holdings
        # unprompted. A search term or filter is required first; only
        # catalogue curators (and administrators) may browse everything.
        if not _has_search_criteria(filters) and (
            Permission.STORE_BROWSE_ALL not in actor.permissions
        ):
            raise AppError(
                422,
                "search_criteria_required",
                "Enter a search term or filter to view store products.",
            )
        scope = self._policy.visibility_scope(actor)
        structured_filters = without_text_query(filters)
        projected_page = self._repository.search_product_page(structured_filters, scope)
        filtered = (
            self._local_filtered_products(actor, structured_filters)
            if projected_page is None
            else ()
        )
        facets = facets_for(filtered) if projected_page is None else projected_page.facets
        if has_text_query(filters):
            query = filters.query.strip() if filters.query else ""
            query_embedding = (
                self._embeddings.embed(
                    query, purpose="store-browse-query", principal_id=actor.user_id
                )
                if self._embeddings is not None
                else None
            )
            hits = hybrid_hits(
                self.hybrid_candidates(
                    actor,
                    filters,
                    query,
                    query_embedding,
                    leg_limit=STORE_BROWSE_HYBRID_LEG_LIMIT,
                ),
                query,
            )
            return paged_result(hits, filters, facets)
        if projected_page is not None:
            visible_page = tuple(
                product
                for product in projected_page.products
                if self._policy.can_read(actor, product)
                and structured_filter_match(product, structured_filters)
            )
            if len(visible_page) != len(projected_page.products):
                return projected_page_result((), 0, filters, StoreFacets((), (), ()))
            return projected_page_result(
                visible_page,
                projected_page.total,
                filters,
                projected_page.facets,
            )
        hits = sort_hits_by_relevance(tuple(exact_text_hit(product) for product in filtered))
        return paged_result(hits, filters, facets)

    def _local_filtered_products(
        self,
        actor: UserAccount,
        filters: StoreSearchFilters,
    ) -> tuple[StoreProduct, ...]:
        return tuple(
            product
            for product in self._repository.list_products()
            if self._policy.can_read(actor, product) and structured_filter_match(product, filters)
        )

    def hybrid_candidates(
        self,
        actor: UserAccount,
        filters: StoreSearchFilters,
        query: str,
        query_embedding: tuple[float, ...] | None,
        leg_limit: int = 50,
    ) -> tuple[StoreHybridCandidate, ...]:
        if Permission.PRODUCT_SEARCH not in actor.permissions:
            raise AppError(403, "forbidden", "Permission denied.")
        candidates = self._repository.hybrid_candidates(
            filters,
            self._policy.visibility_scope(actor),
            query,
            query_embedding,
            leg_limit,
        )
        return tuple(
            candidate for candidate in candidates if self._policy.can_read(actor, candidate.product)
        )


def _has_search_criteria(filters: StoreSearchFilters) -> bool:
    """At least one purposeful criterion beyond pagination."""
    criteria = (
        filters.query,
        filters.product_type,
        filters.region,
        filters.tag,
        filters.source_type,
        filters.status,
        filters.date_from,
        filters.date_to,
        filters.owner_team,
    )
    return any(value not in (None, "") for value in criteria)


@dataclass(frozen=True)
class StoreServices:
    repository: StoreRepository
    ingestion: StoreIngestionService
    search: StoreSearchService
    details: StoreDetailService
    assets: StoreAssetService
    suggestions: MetadataSuggestionService
