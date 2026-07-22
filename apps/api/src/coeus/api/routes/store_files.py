import asyncio
import json
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Annotated, BinaryIO
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request
from pydantic import ValidationError
from starlette.datastructures import UploadFile
from starlette.formparsers import MultiPartException
from starlette.responses import StreamingResponse

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
from coeus.api.upload_limits import UploadWireLimitExceeded, install_receive_limit
from coeus.application.ports.admission import ResourceAdmission
from coeus.core.config import Settings
from coeus.core.deployment import HOSTED_ENVIRONMENTS
from coeus.core.errors import AppError
from coeus.domain.access import ProductStatus
from coeus.domain.auth import AuthenticatedSession, UserAccount
from coeus.domain.store import object_key_segment
from coeus.schemas.store import StoreProductCreateRequest, StoreProductResponse
from coeus.services.asset_tokens import AssetTokenService
from coeus.services.object_storage import ObjectStorage
from coeus.services.product_processing import ProcessedProductFile, process_product_file
from coeus.services.store import StoreServices
from coeus.services.store_asset_redemption import redeemable_asset
from coeus.services.store_creation_policy import (
    require_product_creation_permission,
    require_product_creation_status,
)

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


@dataclass(frozen=True)
class StagedUpload:
    path: Path
    name: str
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
    admission: Annotated[ResourceAdmission, Depends(get_upload_admission)],
) -> StoreProductResponse:
    require_product_creation_permission(authenticated.user)
    try:
        with admission.reserve(authenticated.user.user_id, settings.local_upload_max_bytes):
            staged, product_request = await _parse_and_stage_upload(
                request,
                settings.local_upload_max_bytes,
                authenticated.user,
                hosted_environment=settings.environment in HOSTED_ENVIRONMENTS,
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
    actor: UserAccount,
    *,
    hosted_environment: bool,
) -> tuple[StagedUpload, StoreProductCreateRequest]:
    install_receive_limit(request, max_bytes + MAX_MULTIPART_OVERHEAD_BYTES)
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
            if payload.get("status") == ProductStatus.PUBLISHED.value:
                require_product_creation_status(actor, ProductStatus.PUBLISHED)
            staged = await asyncio.to_thread(
                _stage_upload,
                asset.file,
                asset.filename or "asset",
                max_bytes,
            )
            processed = await asyncio.to_thread(
                process_product_file,
                staged.path,
                staged.name,
                hosted_environment=hosted_environment,
            )
            payload["assets"] = [_asset_payload(staged, processed)]
            return staged, _validated_product_request(payload)
    except Exception:
        if staged is not None:
            staged.path.unlink(missing_ok=True)
        raise


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
    selected = redeemable_asset(
        claims,
        authenticated.user,
        product_id,
        asset_id,
        store_services.details,
    )
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


def _asset_payload(
    staged: StagedUpload,
    processed: ProcessedProductFile,
) -> dict[str, object]:
    return {
        "assetType": processed.asset_type,
        "mimeType": processed.detected_mime_type,
        "name": staged.name,
        "previewKind": processed.preview_kind,
        "sha256": staged.sha256,
        "sizeBytes": staged.size_bytes,
    }
