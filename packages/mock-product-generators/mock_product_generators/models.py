from dataclasses import dataclass, field
from uuid import UUID

MOCK_BANNER = "MOCK DATA ONLY"


@dataclass(frozen=True)
class SeedAsset:
    asset_id: UUID
    name: str
    asset_type: str
    mime_type: str
    size_bytes: int
    sha256: str
    relative_path: str


@dataclass(frozen=True)
class SeedProduct:
    product_id: UUID
    reference: str
    title: str
    summary: str
    description: str
    product_type: str
    source_type: str
    owner_team: str
    area_or_region: str
    classification_level: int
    releasability: tuple[str, ...]
    handling_caveats: tuple[str, ...]
    tags: tuple[str, ...]
    acg_codes: tuple[str, ...]
    access_scenario: str
    assets: tuple[SeedAsset, ...] = field(default_factory=tuple)
    geojson_ref: str | None = None
    bounding_box: tuple[float, float, float, float] | None = None


@dataclass(frozen=True)
class ProductTemplate:
    family: str
    product_type: str
    source_type: str
    owner_team: str
    area_or_region: str
    acg_codes: tuple[str, ...]
    classification_level: int
    asset_formats: tuple[str, ...]
    tags: tuple[str, ...]
