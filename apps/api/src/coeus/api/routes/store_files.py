import json
from hashlib import sha256
from pathlib import PurePath
from typing import Annotated
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Header, UploadFile
from pydantic import ValidationError
from starlette.responses import Response

from coeus.api.dependencies import (
    get_asset_token_service,
    get_csrf_validated_session,
    get_current_session,
    get_object_storage,
    get_settings,
    get_store_services,
)
from coeus.api.presenters.store import product_draft_from_request, product_response
from coeus.core.config import Settings
from coeus.core.errors import AppError
from coeus.domain.auth import AuthenticatedSession
from coeus.domain.store import object_key_segment
from coeus.schemas.store import StoreProductCreateRequest, StoreProductResponse
from coeus.services.asset_tokens import AssetTokenService
from coeus.services.object_storage import ObjectStorage
from coeus.services.store import StoreServices

router = APIRouter(prefix="/store", tags=["store"])
CHUNK_SIZE = 1024 * 1024


@router.post("/products/upload", response_model=StoreProductResponse, status_code=201)
async def upload_product(
    metadata: Annotated[str, Form()],
    asset: Annotated[UploadFile, File()],
    authenticated: Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    storage: Annotated[ObjectStorage, Depends(get_object_storage)],
    store_services: Annotated[StoreServices, Depends(get_store_services)],
) -> StoreProductResponse:
    content = await _read_upload(asset, settings.local_upload_max_bytes)
    payload = _metadata_payload(metadata)
    payload["assets"] = [_asset_payload(asset, content)]
    request = _validated_product_request(payload)
    product = store_services.ingestion.create_existing_product(
        authenticated.user,
        product_draft_from_request(request),
        audit=False,
    )
    try:
        storage.write_bytes(product.assets[0].object_key, content)
    except OSError as exc:
        try:
            storage.delete_bytes(product.assets[0].object_key)
        finally:
            store_services.repository.delete_product(product.product_id)
        raise AppError(
            500,
            "asset_storage_failed",
            "Asset bytes could not be persisted.",
        ) from exc
    try:
        store_services.ingestion.audit_product_created(authenticated.user, product)
    except Exception:
        store_services.repository.delete_product(product.product_id)
        storage.delete_bytes(product.assets[0].object_key)
        raise
    return product_response(product)


@router.get("/products/{product_id}/assets/{asset_id}/download")
def download_asset(
    product_id: UUID,
    asset_id: UUID,
    # The token travels in a header so it never lands in URL logs or history.
    token: Annotated[str, Header(alias="X-Asset-Token", min_length=20)],
    authenticated: Annotated[AuthenticatedSession, Depends(get_current_session)],
    tokens: Annotated[AssetTokenService, Depends(get_asset_token_service)],
    storage: Annotated[ObjectStorage, Depends(get_object_storage)],
    store_services: Annotated[StoreServices, Depends(get_store_services)],
) -> Response:
    claims = tokens.verify(token)
    if (
        claims.user_id != authenticated.user.user_id
        or claims.product_id != product_id
        or claims.asset_id != asset_id
    ):
        raise AppError(403, "asset_token_invalid", "Asset token is invalid.")
    product = (
        store_services.details.get_restricted_product(authenticated.user, product_id)
        if claims.break_glass
        else store_services.details.get_visible_product(authenticated.user, product_id)
    )
    selected = next((asset for asset in product.assets if asset.asset_id == asset_id), None)
    if selected is None:
        raise AppError(404, "asset_not_found", "Asset was not found.")
    if not storage.exists(selected.object_key):
        raise AppError(404, "asset_bytes_not_found", "Asset bytes were not found.")
    filename = quote(object_key_segment(selected.name))
    return Response(
        content=storage.read_bytes(selected.object_key),
        media_type=selected.mime_type,
        # Controlled downloads must never be served from the browser HTTP cache.
        headers={
            "Cache-Control": "no-store",
            "Content-Disposition": f"attachment; filename*=UTF-8''{filename}",
        },
    )


async def _read_upload(asset: UploadFile, max_bytes: int) -> bytes:
    chunks: list[bytes] = []
    size = 0
    while chunk := await asset.read(CHUNK_SIZE):
        size += len(chunk)
        if size > max_bytes:
            raise AppError(413, "asset_too_large", "Asset exceeds the local upload limit.")
        chunks.append(chunk)
    if size == 0:
        raise AppError(409, "asset_empty", "Asset upload cannot be empty.")
    return b"".join(chunks)


def _metadata_payload(metadata: str) -> dict[str, object]:
    try:
        payload = json.loads(metadata)
    except json.JSONDecodeError as exc:
        raise AppError(422, "product_metadata_invalid", "Product metadata must be JSON.") from exc
    if not isinstance(payload, dict):
        raise AppError(422, "product_metadata_invalid", "Product metadata must be an object.")
    return payload


def _validated_product_request(payload: dict[str, object]) -> StoreProductCreateRequest:
    try:
        return StoreProductCreateRequest.model_validate(payload)
    except ValidationError as exc:
        raise AppError(422, "product_metadata_invalid", "Product metadata is invalid.") from exc


def _asset_payload(asset: UploadFile, content: bytes) -> dict[str, object]:
    name = object_key_segment(asset.filename or "asset")
    mime_type = asset.content_type or "application/octet-stream"
    return {
        "assetType": _asset_type(name, mime_type),
        "mimeType": mime_type,
        "name": name,
        "sha256": sha256(content).hexdigest(),
        "sizeBytes": len(content),
    }


def _asset_type(name: str, mime_type: str) -> str:
    suffix = PurePath(name).suffix.removeprefix(".").casefold()
    if suffix:
        return suffix
    return mime_type.split("/", 1)[0] or "binary"
