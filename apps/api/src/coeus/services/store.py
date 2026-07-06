from dataclasses import dataclass
from datetime import UTC, datetime
from re import fullmatch
from uuid import UUID

from coeus.core.errors import AppError
from coeus.core.permissions import Permission
from coeus.domain.access import ProductStatus
from coeus.domain.auth import UserAccount
from coeus.domain.store import (
    AssetAccessGrant,
    BoundingBox,
    MetadataSuggestion,
    StoreAsset,
    StoreFacets,
    StoreProduct,
    StoreProductMetadata,
    StoreSearchFilters,
    StoreSearchHit,
    StoreSearchResult,
)
from coeus.repositories.access import SeedAccessRepository
from coeus.repositories.store import InMemoryStoreRepository, new_store_product_id
from coeus.services.audit import AuditLog
from coeus.services.store_owner_policy import normalise_owner_team, require_owner_permission
from coeus.services.store_search_dates import within_dates

HASH_PATTERN = r"[a-fA-F0-9]{64}"


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
    project_id: UUID | None
    status: ProductStatus
    time_period_start: str | None
    time_period_end: str | None
    geojson_ref: str | None
    bounding_box: BoundingBox | None
    assets: tuple[StoreAsset, ...]


class StoreProductAccessPolicy:
    def __init__(self, access_repository: SeedAccessRepository) -> None:
        self._access_repository = access_repository

    def can_read(self, user: UserAccount, product: StoreProduct) -> bool:
        metadata = product.metadata
        if Permission.PRODUCT_READ not in user.permissions or not user.is_active:
            return False
        if metadata.status == ProductStatus.ARCHIVED:
            return Permission.PRODUCT_READ_RESTRICTED in user.permissions
        if user.clearance_level < metadata.classification_level:
            return False
        if (
            metadata.status == ProductStatus.DRAFT
            and Permission.PRODUCT_MANAGE_ASSETS not in user.permissions
        ):
            return False
        user_acg_ids = self._access_repository.active_acg_ids_for_user(user.user_id)
        return Permission.PRODUCT_READ_RESTRICTED in user.permissions or bool(
            user_acg_ids.intersection(metadata.acg_ids)
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
                project_id=draft.project_id,
                status=draft.status,
                time_period_start=draft.time_period_start,
                time_period_end=draft.time_period_end,
                geojson_ref=draft.geojson_ref,
                bounding_box=draft.bounding_box,
            ),
            assets=self._with_object_keys(draft.assets),
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
                object_key=f"store/uploads/{asset.asset_id}/{asset.name}",
                preview_kind=asset.preview_kind,
            )
            for asset in assets
        )


class StoreSearchService:
    def __init__(
        self, repository: InMemoryStoreRepository, policy: StoreProductAccessPolicy
    ) -> None:
        self._repository = repository
        self._policy = policy

    def search(self, actor: UserAccount, filters: StoreSearchFilters) -> StoreSearchResult:
        if Permission.PRODUCT_SEARCH not in actor.permissions:
            raise AppError(403, "forbidden", "Permission denied.")
        visible = tuple(
            product
            for product in self._repository.list_products()
            if self._policy.can_read(actor, product)
        )
        filtered = tuple(product for product in visible if self._matches_filters(product, filters))
        hits = tuple(
            sorted(
                (self._score(product, filters.query) for product in filtered),
                key=lambda hit: (-hit.match_score, hit.product.metadata.title),
            )
        )
        return StoreSearchResult(hits=hits, total=len(hits), facets=self._facets(filtered))

    @staticmethod
    def _matches_filters(product: StoreProduct, filters: StoreSearchFilters) -> bool:
        metadata = product.metadata
        return all(
            (
                _contains(_search_blob(product), filters.query),
                filters.product_type is None or metadata.product_type == filters.product_type,
                _contains(metadata.area_or_region, filters.region),
                filters.tag is None
                or filters.tag.casefold() in {tag.casefold() for tag in metadata.tags},
                filters.source_type is None or metadata.source_type == filters.source_type,
                filters.status is None or metadata.status == filters.status,
                filters.project_id is None or metadata.project_id == filters.project_id,
                within_dates(metadata, filters.date_from, filters.date_to),
            )
        )

    @staticmethod
    def _score(product: StoreProduct, query: str | None) -> StoreSearchHit:
        if query is None or query.strip() == "":
            return StoreSearchHit(product=product, match_score=1.0, match_reasons=("visible",))
        terms = [term for term in query.casefold().split() if term]
        blob = _search_blob(product).casefold()
        matches = tuple(term for term in terms if term in blob)
        score = len(matches) / max(len(terms), 1)
        return StoreSearchHit(
            product=product, match_score=score, match_reasons=matches or ("visible",)
        )

    @staticmethod
    def _facets(products: tuple[StoreProduct, ...]) -> StoreFacets:
        return StoreFacets(
            product_types=tuple(sorted({product.metadata.product_type for product in products})),
            regions=tuple(sorted({product.metadata.area_or_region for product in products})),
            tags=tuple(sorted({tag for product in products for tag in product.metadata.tags})),
        )


class StoreDetailService:
    def __init__(
        self, repository: InMemoryStoreRepository, policy: StoreProductAccessPolicy
    ) -> None:
        self._repository = repository
        self._policy = policy

    def get_visible_product(self, actor: UserAccount, product_id: UUID) -> StoreProduct:
        product = self._repository.get_product(product_id)
        if product is None or not self._policy.can_read(actor, product):
            raise AppError(404, "product_not_found", "Product was not found.")
        return product


class StoreAssetService:
    def __init__(self, details: StoreDetailService) -> None:
        self._details = details

    def grant_access(
        self, actor: UserAccount, product_id: UUID, asset_id: UUID
    ) -> AssetAccessGrant:
        if Permission.PRODUCT_DOWNLOAD not in actor.permissions:
            raise AppError(403, "forbidden", "Permission denied.")
        product = self._details.get_visible_product(actor, product_id)
        for asset in product.assets:
            if asset.asset_id == asset_id:
                return AssetAccessGrant(
                    asset=asset, download_token=f"asset-token-{asset_id}", expires_in_seconds=900
                )
        raise AppError(404, "asset_not_found", "Asset was not found.")


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
        return MetadataSuggestion(
            tags=tuple(dict.fromkeys(tags)), entities=entities, source_type="synthetic", acg_ids=()
        )


@dataclass(frozen=True)
class StoreServices:
    repository: InMemoryStoreRepository
    ingestion: StoreIngestionService
    search: StoreSearchService
    details: StoreDetailService
    assets: StoreAssetService
    suggestions: MetadataSuggestionService


def build_store_services(
    access_repository: SeedAccessRepository, audit_log: AuditLog
) -> StoreServices:
    repository = InMemoryStoreRepository(access_repository)
    policy = StoreProductAccessPolicy(access_repository)
    details = StoreDetailService(repository, policy)
    return StoreServices(
        repository=repository,
        ingestion=StoreIngestionService(repository, access_repository, audit_log),
        search=StoreSearchService(repository, policy),
        details=details,
        assets=StoreAssetService(details),
        suggestions=MetadataSuggestionService(),
    )


def _search_blob(product: StoreProduct) -> str:
    metadata = product.metadata
    return " ".join(
        (
            metadata.title,
            metadata.summary,
            metadata.description,
            metadata.product_type,
            metadata.source_type,
            metadata.owner_team,
            metadata.area_or_region,
            " ".join(metadata.tags),
        )
    )


def _contains(value: str, needle: str | None) -> bool:
    return needle is None or needle.casefold() in value.casefold()
