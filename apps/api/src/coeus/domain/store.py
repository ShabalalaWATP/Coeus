from dataclasses import dataclass, field
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
    semantic_labels: frozenset[str] = field(default_factory=frozenset)


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


def object_key_segment(name: str) -> str:
    """Reduce a client-supplied asset name to a single safe path segment.

    Object keys are built from a server-generated UUID plus the asset name.
    Stripping any directory components (``/`` or ``\\``) and parent references
    keeps a malicious name from escaping its key prefix once a real object
    store is wired in. The display name on the asset is left untouched.
    """
    segment = name.replace("\\", "/").rsplit("/", 1)[-1].strip()
    if segment in {"", ".", ".."}:
        return "asset"
    return segment


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
    date_from: str | None = None
    date_to: str | None = None
    owner_team: str | None = None
    page: int = 1
    page_size: int = 12


@dataclass(frozen=True)
class StoreVisibilityScope:
    acg_ids: frozenset[UUID]
    clearance_level: int
    include_drafts: bool


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
    page: int
    page_size: int
    total_pages: int
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
    semantic_labels: tuple[str, ...] = ()
