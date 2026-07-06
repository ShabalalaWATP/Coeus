from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Query

from coeus.api.dependencies import (
    get_csrf_validated_session,
    get_current_session,
    get_store_services,
)
from coeus.core.errors import AppError
from coeus.domain.access import ProductStatus
from coeus.domain.auth import AuthenticatedSession
from coeus.domain.store import (
    BoundingBox,
    StoreAsset,
    StoreProduct,
    StoreSearchFilters,
    StoreSearchHit,
)
from coeus.schemas.store import (
    AssetAccessResponse,
    MetadataSuggestionRequest,
    MetadataSuggestionResponse,
    StoreAssetResponse,
    StoreFacetsResponse,
    StoreProductCreateRequest,
    StoreProductResponse,
    StoreProductSearchResponse,
    StoreSearchResponse,
)
from coeus.services.store import StoreProductDraft, StoreServices

router = APIRouter(prefix="/store", tags=["store"])


@router.get("/products", response_model=StoreSearchResponse)
async def search_products(
    authenticated: Annotated[AuthenticatedSession, Depends(get_current_session)],
    store_services: Annotated[StoreServices, Depends(get_store_services)],
    query: str | None = None,
    product_type: Annotated[str | None, Query(alias="productType")] = None,
    region: str | None = None,
    tag: str | None = None,
    source_type: Annotated[str | None, Query(alias="sourceType")] = None,
    status: ProductStatus | None = None,
    project_id: Annotated[UUID | None, Query(alias="projectId")] = None,
    date_from: Annotated[
        str | None, Query(alias="dateFrom", pattern=r"^\d{4}-\d{2}-\d{2}$")
    ] = None,
    date_to: Annotated[str | None, Query(alias="dateTo", pattern=r"^\d{4}-\d{2}-\d{2}$")] = None,
) -> StoreSearchResponse:
    result = store_services.search.search(
        authenticated.user,
        StoreSearchFilters(
            query,
            product_type,
            region,
            tag,
            source_type,
            status,
            project_id,
            date_from,
            date_to,
        ),
    )
    return StoreSearchResponse(
        products=[_to_search_response(hit) for hit in result.hits],
        total=result.total,
        facets=StoreFacetsResponse(
            product_types=list(result.facets.product_types),
            regions=list(result.facets.regions),
            tags=list(result.facets.tags),
        ),
    )


@router.post("/products", response_model=StoreProductResponse, status_code=201)
async def create_product(
    payload: StoreProductCreateRequest,
    authenticated: Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)],
    store_services: Annotated[StoreServices, Depends(get_store_services)],
) -> StoreProductResponse:
    product = store_services.ingestion.create_existing_product(
        authenticated.user,
        _to_product_draft(payload),
    )
    return _to_product_response(product)


@router.get("/products/{product_id}", response_model=StoreProductResponse)
async def get_product(
    product_id: UUID,
    authenticated: Annotated[AuthenticatedSession, Depends(get_current_session)],
    store_services: Annotated[StoreServices, Depends(get_store_services)],
) -> StoreProductResponse:
    return _to_product_response(
        store_services.details.get_visible_product(authenticated.user, product_id)
    )


@router.get("/products/{product_id}/assets/{asset_id}/access", response_model=AssetAccessResponse)
async def get_asset_access(
    product_id: UUID,
    asset_id: UUID,
    authenticated: Annotated[AuthenticatedSession, Depends(get_current_session)],
    store_services: Annotated[StoreServices, Depends(get_store_services)],
) -> AssetAccessResponse:
    grant = store_services.assets.grant_access(authenticated.user, product_id, asset_id)
    return AssetAccessResponse(
        asset_id=grant.asset.asset_id,
        download_token=grant.download_token,
        expires_in_seconds=grant.expires_in_seconds,
    )


@router.post("/metadata-suggestions", response_model=MetadataSuggestionResponse)
async def suggest_metadata(
    payload: MetadataSuggestionRequest,
    _authenticated: Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)],
    store_services: Annotated[StoreServices, Depends(get_store_services)],
) -> MetadataSuggestionResponse:
    suggestion = store_services.suggestions.suggest(
        payload.title,
        payload.summary,
        payload.product_type,
        payload.area_or_region,
    )
    return MetadataSuggestionResponse(
        tags=list(suggestion.tags),
        entities=list(suggestion.entities),
        source_type=suggestion.source_type,
        acg_ids=list(suggestion.acg_ids),
    )


def _to_product_draft(payload: StoreProductCreateRequest) -> StoreProductDraft:
    status = _parse_status(payload.status)
    bounding_box = (
        BoundingBox(
            west=payload.bounding_box.west,
            south=payload.bounding_box.south,
            east=payload.bounding_box.east,
            north=payload.bounding_box.north,
        )
        if payload.bounding_box is not None
        else None
    )
    return StoreProductDraft(
        title=payload.title,
        summary=payload.summary,
        description=payload.description,
        product_type=payload.product_type,
        source_type=payload.source_type,
        owner_team=payload.owner_team,
        area_or_region=payload.area_or_region,
        classification_level=payload.classification_level,
        releasability=frozenset(payload.releasability),
        handling_caveats=frozenset(payload.handling_caveats),
        tags=frozenset(payload.tags),
        acg_ids=frozenset(payload.acg_ids),
        project_id=payload.project_id,
        status=status,
        time_period_start=payload.time_period_start,
        time_period_end=payload.time_period_end,
        geojson_ref=payload.geojson_ref,
        bounding_box=bounding_box,
        assets=tuple(
            StoreAsset(
                asset_id=uuid4(),
                name=asset.name,
                asset_type=asset.asset_type,
                mime_type=asset.mime_type,
                size_bytes=asset.size_bytes,
                sha256=asset.sha256,
                object_key="pending",
                preview_kind=_preview_kind(asset.mime_type, asset.asset_type),
            )
            for asset in payload.assets
        ),
    )


def _parse_status(status: str) -> ProductStatus:
    try:
        return ProductStatus(status)
    except ValueError as exc:
        raise AppError(409, "product_status_invalid", "Product status is not supported.") from exc


def _to_search_response(hit: StoreSearchHit) -> StoreProductSearchResponse:
    product = hit.product
    payload = _product_payload(product)
    payload["match_score"] = hit.match_score
    payload["match_reasons"] = list(hit.match_reasons)
    return StoreProductSearchResponse.model_validate(payload)


def _to_product_response(product: StoreProduct) -> StoreProductResponse:
    return StoreProductResponse.model_validate(_product_payload(product))


def _product_payload(product: StoreProduct) -> dict[str, object]:
    metadata = product.metadata
    return {
        "product_id": product.product_id,
        "reference": product.reference,
        "title": metadata.title,
        "summary": metadata.summary,
        "description": metadata.description,
        "product_type": metadata.product_type,
        "source_type": metadata.source_type,
        "owner_team": metadata.owner_team,
        "area_or_region": metadata.area_or_region,
        "classification_level": metadata.classification_level,
        "releasability": sorted(metadata.releasability),
        "handling_caveats": sorted(metadata.handling_caveats),
        "tags": sorted(metadata.tags),
        "acg_ids": list(metadata.acg_ids),
        "project_id": metadata.project_id,
        "status": metadata.status.value,
        "time_period_start": metadata.time_period_start,
        "time_period_end": metadata.time_period_end,
        "geojson_ref": metadata.geojson_ref,
        "assets": [_to_asset_response(asset) for asset in product.assets],
    }


def _to_asset_response(asset: StoreAsset) -> StoreAssetResponse:
    return StoreAssetResponse(
        asset_id=asset.asset_id,
        name=asset.name,
        asset_type=asset.asset_type,
        mime_type=asset.mime_type,
        size_bytes=asset.size_bytes,
        sha256=asset.sha256,
        preview_kind=asset.preview_kind,
    )


def _preview_kind(mime_type: str, asset_type: str) -> str:
    if mime_type.startswith("image/"):
        return "image"
    if mime_type == "application/geo+json" or asset_type == "geojson":
        return "geojson"
    if mime_type == "application/pdf" or asset_type == "pdf":
        return "pdf_metadata"
    return "text_metadata"
