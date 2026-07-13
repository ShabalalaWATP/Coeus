from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from coeus.domain.access import ProductStatus

_UNSAFE_OBJECT_KEY_CHARS = frozenset('<>:"/\\|?*')
_MAX_OBJECT_KEY_SEGMENT_LENGTH = 180
SYNTHETIC_RELEASABILITY = ("MOCK",)
SYNTHETIC_HANDLING_CAVEATS = ("MOCK DATA ONLY",)
_WINDOWS_RESERVED_BASENAMES = frozenset(
    {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        *(f"COM{index}" for index in range(1, 10)),
        *(f"LPT{index}" for index in range(1, 10)),
    }
)


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
    Stripping directory components, parent references and unsafe filename
    characters keeps a malicious or platform-invalid name from escaping its key
    prefix once a real object store is wired in.
    """
    segment = name.replace("\\", "/").rsplit("/", 1)[-1].strip()
    segment = "".join("_" if _is_unsafe_object_key_character(char) else char for char in segment)
    segment = segment.lstrip(".").rstrip(" .").strip()[:_MAX_OBJECT_KEY_SEGMENT_LENGTH]
    if segment in {"", ".", ".."} or segment.replace("_", "").replace("-", "").strip() == "":
        return "asset"
    if _has_windows_reserved_basename(segment):
        return f"asset-{segment}"[:_MAX_OBJECT_KEY_SEGMENT_LENGTH]
    return segment


def normalise_synthetic_release_markers(
    releasability: list[str] | tuple[str, ...] | frozenset[str],
    handling_caveats: list[str] | tuple[str, ...] | frozenset[str],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Validate the only release markers supported by the synthetic runtime."""

    normalised_releasability = tuple(
        sorted({value.strip().upper() for value in releasability if value.strip()})
    )
    normalised_caveats = tuple(
        sorted({value.strip().upper() for value in handling_caveats if value.strip()})
    )
    if normalised_releasability != SYNTHETIC_RELEASABILITY:
        raise ValueError("releasability must use the synthetic MOCK marker")
    if normalised_caveats != SYNTHETIC_HANDLING_CAVEATS:
        raise ValueError("handling caveats must use the synthetic MOCK DATA ONLY marker")
    return normalised_releasability, normalised_caveats


def _is_unsafe_object_key_character(character: str) -> bool:
    return ord(character) < 32 or ord(character) == 127 or character in _UNSAFE_OBJECT_KEY_CHARS


def _has_windows_reserved_basename(segment: str) -> bool:
    return segment.split(".", 1)[0].upper() in _WINDOWS_RESERVED_BASENAMES


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
    draft_creator_user_id: UUID | None = None


def product_in_scope(product: "StoreProduct", scope: StoreVisibilityScope) -> bool:
    """Mirror the SQL projection scope predicate for the in-memory fallback path.

    Keeps the memory retrieval leg from ranking over products the requester
    cannot see, matching the archived/clearance/draft/ACG filter applied in
    ``store_projection_search_sql``. Security still relies on the service-layer
    ``can_read`` recheck; this only stops hidden products distorting ranks.
    """
    metadata = product.metadata
    if metadata.status == ProductStatus.ARCHIVED:
        return False
    if metadata.classification_level > scope.clearance_level:
        return False
    if (
        metadata.status == ProductStatus.DRAFT
        and not scope.include_drafts
        and scope.draft_creator_user_id != product.created_by_user_id
    ):
        return False
    return bool(metadata.acg_ids & scope.acg_ids)


@dataclass(frozen=True)
class StoreSearchHit:
    product: StoreProduct
    match_score: float
    match_reasons: tuple[str, ...]


@dataclass(frozen=True)
class StoreHybridCandidate:
    product: StoreProduct
    lexical_rank: int | None = None
    lexical_score: float = 0.0
    vector_rank: int | None = None
    vector_score: float = 0.0
    lexical_only: bool = False


@dataclass(frozen=True)
class StoreFacets:
    product_types: tuple[str, ...]
    regions: tuple[str, ...]
    tags: tuple[str, ...]


@dataclass(frozen=True)
class StoreProductSearchPage:
    products: tuple[StoreProduct, ...]
    total: int
    facets: StoreFacets


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
