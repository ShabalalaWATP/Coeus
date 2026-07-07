from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

ISO_DATE_PATTERN = r"^\d{4}-\d{2}-\d{2}$"
ReleasabilityText = Annotated[str, Field(min_length=1, max_length=40)]
HandlingCaveatText = Annotated[str, Field(min_length=1, max_length=120)]
TagText = Annotated[str, Field(min_length=1, max_length=60)]
SemanticLabelText = Annotated[str, Field(min_length=1, max_length=80)]


class BoundingBoxRequest(BaseModel):
    west: float
    south: float
    east: float
    north: float


MAX_ASSET_SIZE_BYTES = 5_000_000_000


class StoreAssetRequest(BaseModel):
    name: str = Field(min_length=3, max_length=180)
    asset_type: str = Field(min_length=2, max_length=80, validation_alias="assetType")
    mime_type: str = Field(min_length=3, max_length=120, validation_alias="mimeType")
    size_bytes: int = Field(le=MAX_ASSET_SIZE_BYTES, validation_alias="sizeBytes")
    sha256: str = Field(min_length=1, max_length=128)


class StoreProductCreateRequest(BaseModel):
    title: str = Field(min_length=3, max_length=180)
    summary: str = Field(min_length=3, max_length=500)
    description: str = Field(min_length=3, max_length=2_000)
    product_type: str = Field(min_length=3, max_length=80, validation_alias="productType")
    source_type: str = Field(min_length=3, max_length=80, validation_alias="sourceType")
    owner_team: str = Field(min_length=2, max_length=80, validation_alias="ownerTeam")
    area_or_region: str = Field(min_length=2, max_length=180, validation_alias="areaOrRegion")
    classification_level: int = Field(ge=0, le=5, validation_alias="classificationLevel")
    releasability: list[ReleasabilityText] = Field(default_factory=list, max_length=12)
    handling_caveats: list[HandlingCaveatText] = Field(
        default_factory=list,
        max_length=12,
        validation_alias="handlingCaveats",
    )
    tags: list[TagText] = Field(default_factory=list, max_length=30)
    semantic_labels: list[SemanticLabelText] = Field(
        default_factory=list,
        max_length=30,
        validation_alias="semanticLabels",
    )
    acg_ids: list[UUID] = Field(default_factory=list, validation_alias="acgIds")
    project_id: UUID | None = Field(default=None, validation_alias="projectId")
    status: str = "published"
    time_period_start: str | None = Field(
        default=None,
        pattern=ISO_DATE_PATTERN,
        validation_alias="timePeriodStart",
    )
    time_period_end: str | None = Field(
        default=None,
        pattern=ISO_DATE_PATTERN,
        validation_alias="timePeriodEnd",
    )
    geojson_ref: str | None = Field(default=None, validation_alias="geojsonRef")
    bounding_box: BoundingBoxRequest | None = Field(default=None, validation_alias="boundingBox")
    assets: list[StoreAssetRequest] = Field(min_length=1)


class MetadataSuggestionRequest(BaseModel):
    title: str = Field(min_length=3, max_length=180)
    summary: str = Field(min_length=3, max_length=500)
    product_type: str = Field(min_length=3, max_length=80, validation_alias="productType")
    area_or_region: str = Field(min_length=2, max_length=180, validation_alias="areaOrRegion")


class BreakGlassProductAccessRequest(BaseModel):
    reason: str = Field(min_length=10, max_length=500)


class StoreAssetResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    asset_id: UUID = Field(serialization_alias="id")
    name: str
    asset_type: str = Field(serialization_alias="assetType")
    mime_type: str = Field(serialization_alias="mimeType")
    size_bytes: int = Field(serialization_alias="sizeBytes")
    sha256: str
    preview_kind: str = Field(serialization_alias="previewKind")


class StoreProductResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    product_id: UUID = Field(serialization_alias="id")
    reference: str
    title: str
    summary: str
    description: str
    product_type: str = Field(serialization_alias="productType")
    source_type: str = Field(serialization_alias="sourceType")
    owner_team: str = Field(serialization_alias="ownerTeam")
    area_or_region: str = Field(serialization_alias="areaOrRegion")
    classification_level: int = Field(serialization_alias="classificationLevel")
    releasability: list[str]
    handling_caveats: list[str] = Field(serialization_alias="handlingCaveats")
    tags: list[str]
    semantic_labels: list[str] = Field(serialization_alias="semanticLabels")
    acg_ids: list[UUID] = Field(serialization_alias="acgIds")
    project_id: UUID | None = Field(serialization_alias="projectId")
    status: str
    time_period_start: str | None = Field(serialization_alias="timePeriodStart")
    time_period_end: str | None = Field(serialization_alias="timePeriodEnd")
    geojson_ref: str | None = Field(serialization_alias="geojsonRef")
    assets: list[StoreAssetResponse]


class StoreProductSearchResponse(StoreProductResponse):
    match_score: float = Field(serialization_alias="matchScore")
    match_reasons: list[str] = Field(serialization_alias="matchReasons")


class StoreFacetsResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    product_types: list[str] = Field(serialization_alias="productTypes")
    regions: list[str]
    tags: list[str]


class StoreSearchResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    products: list[StoreProductSearchResponse]
    total: int
    page: int
    page_size: int = Field(serialization_alias="pageSize")
    total_pages: int = Field(serialization_alias="totalPages")
    facets: StoreFacetsResponse


class AssetAccessResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    asset_id: UUID = Field(serialization_alias="assetId")
    download_token: str = Field(serialization_alias="downloadToken")
    expires_in_seconds: int = Field(serialization_alias="expiresInSeconds")


class MetadataSuggestionResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    tags: list[str]
    entities: list[str]
    source_type: str = Field(serialization_alias="sourceType")
    acg_ids: list[UUID] = Field(serialization_alias="acgIds")
    semantic_labels: list[str] = Field(serialization_alias="semanticLabels")
