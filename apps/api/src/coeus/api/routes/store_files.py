import asyncio
import json
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path, PurePath
from tempfile import NamedTemporaryFile
from typing import Annotated, BinaryIO
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request
from pydantic import ValidationError
from starlette.datastructures import UploadFile
from starlette.formparsers import MultiPartException
from starlette.responses import StreamingResponse
from starlette.types import Message, Receive

from coeus.api.dependencies import (
    get_asset_token_service,
    get_csrf_validated_session,
    get_current_session,
    get_object_storage,
    get_settings,
    get_store_services,
    get_upload_admission,
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
from coeus.services.upload_admission import UploadAdmissionController

router = APIRouter(prefix="/store", tags=["store"])
CHUNK_SIZE = 1024 * 1024
MAX_METADATA_PART_BYTES = 64 * 1024
MAX_MULTIPART_OVERHEAD_BYTES = 256 * 1024

UPLOAD_OPENAPI = {
    "requestBody": {
        "required": True,
        "content": {
            "multipart/form-data": {
                "schema": {
                    "type": "object",
                    "required": ["metadata", "asset"],
                    "properties": {
                        "metadata": {"type": "string", "title": "Metadata"},
                        "asset": {
                            "type": "string",
                            "contentMediaType": "application/octet-stream",
                            "title": "Asset",
                        },
                    },
                }
            }
        },
    }
}


class UploadWireLimitExceeded(Exception):
    """The cumulative request body exceeded its receive-time budget."""


@dataclass(frozen=True)
class StagedUpload:
    path: Path
    name: str
    mime_type: str
    size_bytes: int
    sha256: str


@router.post(
    "/products/upload",
    response_model=StoreProductResponse,
    status_code=201,
    openapi_extra=UPLOAD_OPENAPI,
)
async def upload_product(
    request: Request,
    authenticated: Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    storage: Annotated[ObjectStorage, Depends(get_object_storage)],
    store_services: Annotated[StoreServices, Depends(get_store_services)],
    admission: Annotated[UploadAdmissionController, Depends(get_upload_admission)],
) -> StoreProductResponse:
    try:
        with admission.reserve(authenticated.user.user_id, settings.local_upload_max_bytes):
            staged, product_request = await _parse_and_stage_upload(
                request, settings.local_upload_max_bytes
            )
            try:
                product = store_services.ingestion.create_existing_product(
                    authenticated.user,
                    product_draft_from_request(product_request),
                    audit=False,
                )
                try:
                    await asyncio.to_thread(
                        storage.write_file, product.assets[0].object_key, staged.path
                    )
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
            finally:
                staged.path.unlink(missing_ok=True)
    except UploadWireLimitExceeded as exc:
        raise AppError(413, "asset_too_large", "Asset exceeds the local upload limit.") from exc
    except MultiPartException as exc:
        raise AppError(422, "product_upload_invalid", "Upload form is invalid.") from exc
    raise AssertionError("Upload handling exited without a response.")


async def _parse_and_stage_upload(
    request: Request,
    max_bytes: int,
) -> tuple[StagedUpload, StoreProductCreateRequest]:
    _install_receive_limit(request, max_bytes + MAX_MULTIPART_OVERHEAD_BYTES)
    staged: StagedUpload | None = None
    try:
        async with request.form(
            max_files=1,
            max_fields=1,
            max_part_size=MAX_METADATA_PART_BYTES,
        ) as form:
            metadata = form.get("metadata")
            asset = form.get("asset")
            if not isinstance(metadata, str) or not isinstance(asset, UploadFile):
                raise AppError(422, "product_upload_invalid", "Upload form is invalid.")
            payload = _metadata_payload(metadata)
            staged = await asyncio.to_thread(
                _stage_upload,
                asset.file,
                asset.filename or "asset",
                asset.content_type or "application/octet-stream",
                max_bytes,
            )
            payload["assets"] = [_asset_payload(staged)]
            return staged, _validated_product_request(payload)
    except Exception:
        if staged is not None:
            staged.path.unlink(missing_ok=True)
        raise


def _install_receive_limit(request: Request, max_wire_bytes: int) -> None:
    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            declared_length = int(content_length)
        except ValueError as exc:
            raise AppError(400, "content_length_invalid", "Content-Length is invalid.") from exc
        if declared_length < 0:
            raise AppError(400, "content_length_invalid", "Content-Length is invalid.")
        if declared_length > max_wire_bytes:
            raise UploadWireLimitExceeded
    original_receive: Receive = request._receive
    received = 0

    async def limited_receive() -> Message:
        nonlocal received
        message = await original_receive()
        if message["type"] == "http.request":
            received += len(message.get("body", b""))
            if received > max_wire_bytes:
                raise UploadWireLimitExceeded
        return message

    request._receive = limited_receive


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
) -> StreamingResponse:
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
    return StreamingResponse(
        storage.iter_bytes(selected.object_key, CHUNK_SIZE),
        media_type=selected.mime_type,
        # Controlled downloads must never be served from the browser HTTP cache.
        headers={
            "Cache-Control": "no-store",
            "Content-Disposition": f"attachment; filename*=UTF-8''{filename}",
        },
    )


def _stage_upload(
    source: BinaryIO,
    filename: str,
    mime_type: str,
    max_bytes: int,
) -> StagedUpload:
    size = 0
    digest = sha256()
    path: Path | None = None
    try:
        with NamedTemporaryFile(prefix="coeus-upload-", suffix=".stage", delete=False) as target:
            path = Path(target.name)
            while chunk := source.read(CHUNK_SIZE):
                size += len(chunk)
                if size > max_bytes:
                    raise AppError(413, "asset_too_large", "Asset exceeds the local upload limit.")
                digest.update(chunk)
                target.write(chunk)
        if size == 0:
            raise AppError(409, "asset_empty", "Asset upload cannot be empty.")
        return StagedUpload(
            path=path,
            name=object_key_segment(filename),
            mime_type=mime_type,
            size_bytes=size,
            sha256=digest.hexdigest(),
        )
    except Exception:
        if path is not None:
            path.unlink(missing_ok=True)
        raise


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


def _asset_payload(staged: StagedUpload) -> dict[str, object]:
    return {
        "assetType": _asset_type(staged.name, staged.mime_type),
        "mimeType": staged.mime_type,
        "name": staged.name,
        "sha256": staged.sha256,
        "sizeBytes": staged.size_bytes,
    }


def _asset_type(name: str, mime_type: str) -> str:
    suffix = PurePath(name).suffix.removeprefix(".").casefold()
    if suffix:
        return suffix
    return mime_type.split("/", 1)[0] or "binary"
