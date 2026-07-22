"""Authorised inline previews for released Intelligence Store assets."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Response

from coeus.api.dependencies import (
    get_asset_token_service,
    get_current_session,
    get_object_storage,
    get_store_services,
)
from coeus.core.errors import AppError
from coeus.domain.auth import AuthenticatedSession
from coeus.services.asset_tokens import AssetTokenService
from coeus.services.document_extraction import DocumentExtractionError, extract_pages
from coeus.services.object_storage import ObjectStorage
from coeus.services.store import StoreServices
from coeus.services.store_asset_redemption import redeemable_asset

router = APIRouter(prefix="/store", tags=["store"])


@router.get("/products/{product_id}/assets/{asset_id}/preview")
def preview_store_asset(
    product_id: UUID,
    asset_id: UUID,
    token: Annotated[str, Header(alias="X-Asset-Token", min_length=20)],
    authenticated: Annotated[AuthenticatedSession, Depends(get_current_session)],
    tokens: Annotated[AssetTokenService, Depends(get_asset_token_service)],
    storage: Annotated[ObjectStorage, Depends(get_object_storage)],
    store: Annotated[StoreServices, Depends(get_store_services)],
) -> Response:
    claims = tokens.verify(token)
    asset = redeemable_asset(
        claims,
        authenticated.user,
        product_id,
        asset_id,
        store.details,
    )
    if not storage.exists(asset.object_key):
        raise AppError(404, "asset_not_found", "Asset was not found.")
    content = storage.read_bytes(asset.object_key)
    headers = {
        "Cache-Control": "no-store",
        "Content-Security-Policy": "default-src 'none'; sandbox",
        "X-Content-Type-Options": "nosniff",
    }
    if asset.preview_kind in {"image", "pdf", "pdf_metadata"}:
        return Response(content, media_type=asset.mime_type, headers=headers)
    try:
        pages = extract_pages(content, asset.mime_type)
    except DocumentExtractionError:
        raise AppError(409, "preview_unavailable", "A safe preview is not available.") from None
    preview = "\n\n".join(f"Page or slide {page.page_number}\n{page.text}" for page in pages)
    return Response(preview, media_type="text/plain; charset=utf-8", headers=headers)
