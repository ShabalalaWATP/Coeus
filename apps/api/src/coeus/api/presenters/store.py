from uuid import uuid4

from coeus.core.errors import AppError
from coeus.domain.access import ProductStatus
from coeus.domain.store import (
    BoundingBox,
    StoreAsset,
    StoreProduct,
    StoreSearchHit,
    StoreSearchResult,
)
from coeus.schemas.store import (
    StoreAssetRequest,
    StoreAssetResponse,
    StoreFacetsResponse,
    StoreProductCreateRequest,
    StoreProductResponse,
    StoreProductSearchResponse,
    StoreSearchResponse,
)
from coeus.services.store import StoreProductDraft
from coeus.services.store_semantics import effective_semantic_labels


def store_search_response(result: StoreSearchResult) -> StoreSearchResponse:
    return StoreSearchResponse(
        products=[_search_hit_response(hit) for hit in result.hits],
        total=result.total,
        page=result.page,
        page_size=result.page_size,
        total_pages=result.total_pages,
        facets=StoreFacetsResponse(
            product_types=list(result.facets.product_types),
            regions=list(result.facets.regions),
            tags=list(result.facets.tags),
        ),
    )


def product_draft_from_request(payload: StoreProductCreateRequest) -> StoreProductDraft:
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
        semantic_labels=frozenset(payload.semantic_labels),
        acg_ids=frozenset(payload.acg_ids),
        status=_parse_status(payload.status),
        time_period_start=payload.time_period_start,
        time_period_end=payload.time_period_end,
        geojson_ref=payload.geojson_ref,
        bounding_box=bounding_box,
        assets=tuple(_asset_from_request(asset) for asset in payload.assets),
    )


def product_response(product: StoreProduct) -> StoreProductResponse:
    return StoreProductResponse.model_validate(_product_payload(product))


def _search_hit_response(hit: StoreSearchHit) -> StoreProductSearchResponse:
    payload = _product_payload(hit.product)
    payload["match_score"] = hit.match_score
    payload["match_reasons"] = list(hit.match_reasons)
    return StoreProductSearchResponse.model_validate(payload)


def _asset_from_request(asset: StoreAssetRequest) -> StoreAsset:
    return StoreAsset(
        asset_id=uuid4(),
        name=asset.name,
        asset_type=asset.asset_type,
        mime_type=asset.mime_type,
        size_bytes=asset.size_bytes,
        sha256=asset.sha256,
        object_key="pending",
        preview_kind=_preview_kind(asset.mime_type, asset.asset_type),
    )


def _parse_status(status: str) -> ProductStatus:
    try:
        return ProductStatus(status)
    except ValueError as exc:
        raise AppError(409, "product_status_invalid", "Product status is not supported.") from exc


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
        "semantic_labels": sorted(effective_semantic_labels(product)),
        "acg_ids": list(metadata.acg_ids),
        "status": metadata.status.value,
        "time_period_start": metadata.time_period_start,
        "time_period_end": metadata.time_period_end,
        "geojson_ref": metadata.geojson_ref,
        "assets": [_asset_response(asset) for asset in product.assets],
    }


def _asset_response(asset: StoreAsset) -> StoreAssetResponse:
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
