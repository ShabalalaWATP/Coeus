from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response

from coeus.api.dependencies import (
    get_csrf_validated_session,
    get_current_session,
    get_store_services,
)
from coeus.api.presenters.store import (
    product_draft_from_request,
    product_response,
    store_search_response,
)
from coeus.domain.access import ProductStatus
from coeus.domain.auth import AuthenticatedSession
from coeus.domain.store import StoreSearchFilters
from coeus.schemas.store import (
    AssetAccessResponse,
    BreakGlassProductAccessRequest,
    MetadataSuggestionRequest,
    MetadataSuggestionResponse,
    StoreProductCreateRequest,
    StoreProductResponse,
    StoreSearchResponse,
)
from coeus.services.store import StoreServices

router = APIRouter(prefix="/store", tags=["store"])
SEARCH_TEXT_MAX_LENGTH = 200
SEARCH_FIELD_MAX_LENGTH = 80
SEARCH_REGION_MAX_LENGTH = 180


@router.get("/products", response_model=StoreSearchResponse)
async def search_products(
    authenticated: Annotated[AuthenticatedSession, Depends(get_current_session)],
    store_services: Annotated[StoreServices, Depends(get_store_services)],
    query: Annotated[str | None, Query(max_length=SEARCH_TEXT_MAX_LENGTH)] = None,
    product_type: Annotated[
        str | None, Query(alias="productType", max_length=SEARCH_FIELD_MAX_LENGTH)
    ] = None,
    region: Annotated[str | None, Query(max_length=SEARCH_REGION_MAX_LENGTH)] = None,
    tag: Annotated[str | None, Query(max_length=SEARCH_FIELD_MAX_LENGTH)] = None,
    source_type: Annotated[
        str | None, Query(alias="sourceType", max_length=SEARCH_FIELD_MAX_LENGTH)
    ] = None,
    status: ProductStatus | None = None,
    date_from: Annotated[
        str | None, Query(alias="dateFrom", pattern=r"^\d{4}-\d{2}-\d{2}$")
    ] = None,
    date_to: Annotated[str | None, Query(alias="dateTo", pattern=r"^\d{4}-\d{2}-\d{2}$")] = None,
    owner_team: Annotated[str | None, Query(alias="ownerTeam", min_length=2, max_length=80)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(alias="pageSize", ge=1, le=50)] = 12,
) -> StoreSearchResponse:
    result = store_services.search.search(
        authenticated.user,
        StoreSearchFilters(
            query=query,
            product_type=product_type,
            region=region,
            tag=tag,
            source_type=source_type,
            status=status,
            date_from=date_from,
            date_to=date_to,
            owner_team=owner_team,
            page=page,
            page_size=page_size,
        ),
    )
    return store_search_response(result)


@router.post("/products", response_model=StoreProductResponse, status_code=201)
async def create_product(
    payload: StoreProductCreateRequest,
    authenticated: Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)],
    store_services: Annotated[StoreServices, Depends(get_store_services)],
) -> StoreProductResponse:
    product = store_services.ingestion.create_existing_product(
        authenticated.user,
        product_draft_from_request(payload),
    )
    return product_response(product)


@router.get("/products/{product_id}", response_model=StoreProductResponse)
async def get_product(
    product_id: UUID,
    authenticated: Annotated[AuthenticatedSession, Depends(get_current_session)],
    store_services: Annotated[StoreServices, Depends(get_store_services)],
) -> StoreProductResponse:
    return product_response(
        store_services.details.get_visible_product(authenticated.user, product_id)
    )


@router.post("/products/{product_id}/break-glass", response_model=StoreProductResponse)
async def break_glass_product_access(
    product_id: UUID,
    payload: BreakGlassProductAccessRequest,
    authenticated: Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)],
    store_services: Annotated[StoreServices, Depends(get_store_services)],
) -> StoreProductResponse:
    return product_response(
        store_services.details.get_break_glass_product(
            authenticated.user, product_id, payload.reason
        )
    )


@router.get("/products/{product_id}/assets/{asset_id}/access", response_model=AssetAccessResponse)
async def get_asset_access(
    product_id: UUID,
    asset_id: UUID,
    authenticated: Annotated[AuthenticatedSession, Depends(get_current_session)],
    store_services: Annotated[StoreServices, Depends(get_store_services)],
    response: Response,
) -> AssetAccessResponse:
    grant = store_services.assets.grant_access(authenticated.user, product_id, asset_id)
    # Short-lived download tokens must never be served from the browser HTTP cache.
    response.headers["Cache-Control"] = "no-store"
    return AssetAccessResponse(
        asset_id=grant.asset.asset_id,
        download_token=grant.download_token,
        expires_in_seconds=grant.expires_in_seconds,
    )


@router.post(
    "/products/{product_id}/assets/{asset_id}/break-glass-access",
    response_model=AssetAccessResponse,
)
async def get_break_glass_asset_access(
    product_id: UUID,
    asset_id: UUID,
    payload: BreakGlassProductAccessRequest,
    authenticated: Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)],
    store_services: Annotated[StoreServices, Depends(get_store_services)],
    response: Response,
) -> AssetAccessResponse:
    grant = store_services.assets.grant_break_glass_access(
        authenticated.user, product_id, asset_id, payload.reason
    )
    response.headers["Cache-Control"] = "no-store"
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
        semantic_labels=list(suggestion.semantic_labels),
    )
