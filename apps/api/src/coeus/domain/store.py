from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from coeus.domain.access import ProductStatus


@dataclass(frozen=True)
class BoundingBox:
    west: float
    south: float
    east: float
    north: float


@dataclass(frozen=True)
class StoreProductMetadata:
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


@dataclass(frozen=True)
class StoreAsset:
    asset_id: UUID
    name: str
    asset_type: str
    mime_type: str
    size_bytes: int
    sha256: str
    object_key: str
    preview_kind: str


@dataclass(frozen=True)
class StoreProduct:
    product_id: UUID
    reference: str
    metadata: StoreProductMetadata
    assets: tuple[StoreAsset, ...]
    created_by_user_id: UUID
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class StoreSearchFilters:
    query: str | None = None
    product_type: str | None = None
    region: str | None = None
    tag: str | None = None
    source_type: str | None = None
    status: ProductStatus | None = None
    project_id: UUID | None = None


@dataclass(frozen=True)
class StoreSearchHit:
    product: StoreProduct
    match_score: float
    match_reasons: tuple[str, ...]


@dataclass(frozen=True)
class StoreFacets:
    product_types: tuple[str, ...]
    regions: tuple[str, ...]
    tags: tuple[str, ...]


@dataclass(frozen=True)
class StoreSearchResult:
    hits: tuple[StoreSearchHit, ...]
    total: int
    facets: StoreFacets


@dataclass(frozen=True)
class AssetAccessGrant:
    asset: StoreAsset
    download_token: str
    expires_in_seconds: int


@dataclass(frozen=True)
class MetadataSuggestion:
    tags: tuple[str, ...]
    entities: tuple[str, ...]
    source_type: str
    acg_ids: tuple[UUID, ...]
