from dataclasses import dataclass, field
from datetime import UTC, datetime
from re import fullmatch
from uuid import UUID

from coeus.core.errors import AppError
from coeus.core.permissions import Permission
from coeus.domain.access import ProductStatus
from coeus.domain.auth import UserAccount
from coeus.domain.store import (
    BoundingBox,
    MetadataSuggestion,
    StoreAsset,
    StoreHybridCandidate,
    StoreProduct,
    StoreProductMetadata,
    StoreSearchFilters,
    StoreSearchResult,
    StoreVisibilityScope,
    object_key_segment,
)
from coeus.domain.store_filters import structured_filter_match
from coeus.repositories.access import SeedAccessRepository
from coeus.repositories.store import InMemoryStoreRepository
from coeus.repositories.store_ids import new_store_product_id
from coeus.services.audit import AuditLog
from coeus.services.embeddings import EmbeddingService
from coeus.services.store_access import StoreAssetService, StoreDetailService
from coeus.services.store_owner_policy import normalise_owner_team, require_owner_permission
from coeus.services.store_search_results import (
    exact_text_hit,
    facets_for,
    has_text_query,
    hybrid_hits,
    paged_result,
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


class StoreProductAccessPolicy:
    def __init__(self, access_repository: SeedAccessRepository) -> None:
        self._access_repository = access_repository

    def can_read(self, user: UserAccount, product: StoreProduct) -> bool:
        metadata = product.metadata
        if Permission.PRODUCT_READ not in user.permissions or not user.is_active:
            return False
        if metadata.status == ProductStatus.ARCHIVED:
            return False
        if user.clearance_level < metadata.classification_level:
            return False
        if (
            metadata.status == ProductStatus.DRAFT
            and Permission.PRODUCT_MANAGE_ASSETS not in user.permissions
        ):
            return False
        user_acg_ids = self._access_repository.active_acg_ids_for_user(user.user_id)
        return bool(user_acg_ids.intersection(metadata.acg_ids))

    def visibility_scope(self, user: UserAccount) -> StoreVisibilityScope:
        return StoreVisibilityScope(
            acg_ids=self._access_repository.active_acg_ids_for_user(user.user_id),
            clearance_level=user.clearance_level,
            include_drafts=Permission.PRODUCT_MANAGE_ASSETS in user.permissions,
        )


class StoreIngestionService:
    def __init__(
        self,
        repository: InMemoryStoreRepository,
        access_repository: SeedAccessRepository,
        audit_log: AuditLog,
    ) -> None:
        self._repository = repository
        self._access_repository = access_repository
        self._audit_log = audit_log

    def create_existing_product(self, actor: UserAccount, draft: StoreProductDraft) -> StoreProduct:
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
        self._audit_log.record(
            "product_created",
            str(actor.user_id),
            {"product_id": str(product.product_id), "reference": product.reference},
        )
        return product

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
        repository: InMemoryStoreRepository,
        policy: StoreProductAccessPolicy,
        embeddings: EmbeddingService | None = None,
    ) -> None:
        self._repository = repository
        self._policy = policy
        self._embeddings = embeddings

    def search(self, actor: UserAccount, filters: StoreSearchFilters) -> StoreSearchResult:
        if Permission.PRODUCT_SEARCH not in actor.permissions:
            raise AppError(403, "forbidden", "Permission denied.")
        scope = self._policy.visibility_scope(actor)
        structured_filters = without_text_query(filters)
        candidates = self._repository.search_products(structured_filters, scope)
        visible = tuple(product for product in candidates if self._policy.can_read(actor, product))
        filtered = tuple(
            product for product in visible if structured_filter_match(product, structured_filters)
        )
        facets = facets_for(filtered)
        if has_text_query(filters):
            query = filters.query.strip() if filters.query else ""
            query_embedding = (
                self._embeddings.embed(query, purpose="store-browse-query")
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
        else:
            hits = sort_hits_by_relevance(tuple(exact_text_hit(product) for product in filtered))
        return paged_result(hits, filters, facets)

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


class MetadataSuggestionService:
    def suggest(
        self, title: str, summary: str, product_type: str, area_or_region: str
    ) -> MetadataSuggestion:
        text = f"{title} {summary} {product_type} {area_or_region}".casefold()
        tags = []
        if "baltic" in text:
            tags.append("baltic")
        if product_type == "geographic_product":
            tags.append("geographic")
        tags.append("mock")
        entities = (area_or_region, "MOCK DATA ONLY")
        labels = derive_semantic_labels(title, summary, product_type, area_or_region)
        return MetadataSuggestion(
            tags=tuple(dict.fromkeys(tags)),
            entities=entities,
            source_type="synthetic",
            acg_ids=(),
            semantic_labels=tuple(labels),
        )


@dataclass(frozen=True)
class StoreServices:
    repository: InMemoryStoreRepository
    ingestion: StoreIngestionService
    search: StoreSearchService
    details: StoreDetailService
    assets: StoreAssetService
    suggestions: MetadataSuggestionService
