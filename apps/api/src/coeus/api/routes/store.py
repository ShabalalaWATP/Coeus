from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response

from coeus.api.dependencies import (
    get_csrf_validated_session,
    get_current_session,
    get_search_admission,
    get_store_services,
)
from coeus.api.presenters.store import (
    product_draft_from_request,
    product_response,
    store_search_response,
)
from coeus.application.ports.admission import ResourceAdmission
from coeus.core.async_work import run_bounded_search
from coeus.core.errors import AppError
from coeus.domain.access import ProductStatus
from coeus.domain.auth import AuthenticatedSession
from coeus.domain.store import StoreSearchFilters, StoreSortOrder
from coeus.schemas.store import (
    AssetAccessResponse,
    BreakGlassProductAccessRequest,
    MetadataSuggestionRequest,
    MetadataSuggestionResponse,
    StoreProductCreateRequest,
    StoreProductResponse,
    StoreSearchResponse,
)
from coeus.schemas.store_library import (
    PersonalFolderCreateRequest,
    PersonalFolderResponse,
    PersonalLibraryResponse,
    SavedProductRequest,
    SavedProductResponse,
)
from coeus.services.store import StoreServices

router = APIRouter(prefix="/store", tags=["store"])
SEARCH_TEXT_MAX_LENGTH = 200
SEARCH_FIELD_MAX_LENGTH = 80
SEARCH_REGION_MAX_LENGTH = 180


@router.get("/library", response_model=PersonalLibraryResponse)
async def get_personal_library(
    authenticated: Annotated[AuthenticatedSession, Depends(get_current_session)],
    store_services: Annotated[StoreServices, Depends(get_store_services)],
) -> PersonalLibraryResponse:
    library = store_services.library.list_for_user(authenticated.user.user_id)
    visible: list[SavedProductResponse] = []
    unavailable_count = 0
    for saved in library.saved_products:
        try:
            product = store_services.details.get_visible_product(
                authenticated.user, saved.product_id
            )
        except AppError as exc:
            if exc.status_code != 404:
                raise
            unavailable_count += 1
            continue
        visible.append(
            SavedProductResponse(
                product=product_response(product),
                folder_id=saved.folder_id,
                saved_at=saved.saved_at,
            )
        )
    return PersonalLibraryResponse(
        folders=[
            PersonalFolderResponse(
                folder_id=folder.folder_id,
                name=folder.name,
                created_at=folder.created_at,
            )
            for folder in library.folders
        ],
        saved_products=visible,
        unavailable_count=unavailable_count,
    )


@router.post("/library/folders", response_model=PersonalFolderResponse, status_code=201)
async def create_personal_folder(
    payload: PersonalFolderCreateRequest,
    authenticated: Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)],
    store_services: Annotated[StoreServices, Depends(get_store_services)],
) -> PersonalFolderResponse:
    folder = store_services.library.create_folder(authenticated.user.user_id, payload.name)
    return PersonalFolderResponse(
        folder_id=folder.folder_id, name=folder.name, created_at=folder.created_at
    )


@router.delete("/library/folders/{folder_id}", status_code=204)
async def delete_personal_folder(
    folder_id: UUID,
    authenticated: Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)],
    store_services: Annotated[StoreServices, Depends(get_store_services)],
) -> Response:
    store_services.library.delete_folder(authenticated.user.user_id, folder_id)
    return Response(status_code=204)


@router.put("/library/products/{product_id}", response_model=SavedProductResponse)
async def save_personal_product(
    product_id: UUID,
    payload: SavedProductRequest,
    authenticated: Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)],
    store_services: Annotated[StoreServices, Depends(get_store_services)],
) -> SavedProductResponse:
    product = store_services.details.get_visible_product(authenticated.user, product_id)
    saved = store_services.library.save_product(
        authenticated.user.user_id, product_id, payload.folder_id
    )
    return SavedProductResponse(
        product=product_response(product), folder_id=saved.folder_id, saved_at=saved.saved_at
    )


@router.delete("/library/products/{product_id}", status_code=204)
async def remove_personal_product(
    product_id: UUID,
    authenticated: Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)],
    store_services: Annotated[StoreServices, Depends(get_store_services)],
) -> Response:
    store_services.library.remove_product(authenticated.user.user_id, product_id)
    return Response(status_code=204)


@router.get("/products", response_model=StoreSearchResponse)
async def search_products(
    authenticated: Annotated[AuthenticatedSession, Depends(get_current_session)],
    store_services: Annotated[StoreServices, Depends(get_store_services)],
    admission: Annotated[ResourceAdmission, Depends(get_search_admission)],
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
    sort: StoreSortOrder = StoreSortOrder.RELEVANCE,
) -> StoreSearchResponse:
    with admission.reserve(authenticated.user.user_id):
        result = await run_bounded_search(
            store_services.search.search,
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
                sort=sort,
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
