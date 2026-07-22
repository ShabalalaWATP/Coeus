"""Real external product upload and protected workflow preview routes."""

import asyncio
import json
from hashlib import sha256
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Annotated, BinaryIO
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response
from pydantic import ValidationError
from starlette.datastructures import UploadFile
from starlette.formparsers import MultiPartException

from coeus.api.dependencies import (
    get_analyst_workflow_service,
    get_csrf_validated_session,
    get_current_session,
    get_settings,
    get_upload_admission,
)
from coeus.api.presenters.analyst import task_response
from coeus.api.product_dependencies import (
    get_product_submission_service,
    get_workflow_draft_access_service,
)
from coeus.api.upload_limits import UploadWireLimitExceeded, install_receive_limit
from coeus.application.ports.admission import ResourceAdmission
from coeus.core.config import Settings
from coeus.core.errors import AppError
from coeus.domain.auth import AuthenticatedSession
from coeus.domain.store import object_key_segment
from coeus.schemas.analyst import AnalystTaskResponse, ProductSubmissionMetadataRequest
from coeus.services.analyst_workflow import AnalystWorkflowService
from coeus.services.product_submissions import (
    ProductSubmissionService,
    StagedSubmissionFile,
    SubmissionMetadata,
)
from coeus.services.workflow_draft_access import WorkflowDraftAccessService

router = APIRouter(tags=["analyst"])
CHUNK_SIZE = 1024 * 1024
MAX_METADATA_BYTES = 64 * 1024
MAX_MULTIPART_OVERHEAD_BYTES = 256 * 1024


@router.post(
    "/analyst/tasks/{ticket_id}/submissions/upload",
    response_model=AnalystTaskResponse,
    status_code=201,
)
async def upload_product_submission(
    ticket_id: UUID,
    request: Request,
    authenticated: Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    submissions: Annotated[ProductSubmissionService, Depends(get_product_submission_service)],
    analyst: Annotated[AnalystWorkflowService, Depends(get_analyst_workflow_service)],
    admission: Annotated[ResourceAdmission, Depends(get_upload_admission)],
) -> AnalystTaskResponse:
    submissions.authorise_upload(authenticated.user, ticket_id)
    try:
        with admission.reserve(authenticated.user.user_id, settings.local_upload_max_bytes):
            staged, payload = await _stage_request(request, settings.local_upload_max_bytes)
            try:
                submissions.create(authenticated.user, ticket_id, _metadata(payload), staged)
            finally:
                staged.path.unlink(missing_ok=True)
    except UploadWireLimitExceeded as exc:
        raise AppError(413, "asset_too_large", "Asset exceeds the local upload limit.") from exc
    except MultiPartException as exc:
        raise AppError(422, "product_upload_invalid", "Upload form is invalid.") from exc
    ticket = analyst.task_details(authenticated.user, ticket_id)
    return task_response(ticket, authenticated.user, analyst)


@router.get("/workflow/products/{ticket_id}/versions/{version_id}/assets/{asset_id}/preview")
async def preview_product_submission(
    ticket_id: UUID,
    version_id: UUID,
    asset_id: UUID,
    authenticated: Annotated[AuthenticatedSession, Depends(get_current_session)],
    drafts: Annotated[WorkflowDraftAccessService, Depends(get_workflow_draft_access_service)],
) -> Response:
    preview = drafts.preview(authenticated.user, ticket_id, version_id, asset_id)
    asset = preview.asset
    headers = {
        "Cache-Control": "no-store",
        "Content-Security-Policy": "default-src 'none'; sandbox",
        "X-Content-Type-Options": "nosniff",
    }
    if asset.preview_kind == "text":
        return Response(
            asset.extracted_text, media_type="text/plain; charset=utf-8", headers=headers
        )
    return Response(preview.content, media_type=asset.detected_mime_type, headers=headers)


async def _stage_request(
    request: Request, max_bytes: int
) -> tuple[StagedSubmissionFile, ProductSubmissionMetadataRequest]:
    install_receive_limit(request, max_bytes + MAX_MULTIPART_OVERHEAD_BYTES)
    staged: StagedSubmissionFile | None = None
    try:
        async with request.form(
            max_files=1, max_fields=1, max_part_size=MAX_METADATA_BYTES
        ) as form:
            raw_metadata = form.get("metadata")
            asset = form.get("asset")
            if not isinstance(raw_metadata, str) or not isinstance(asset, UploadFile):
                raise AppError(422, "product_upload_invalid", "Upload form is invalid.")
            payload = _validate_metadata(raw_metadata)
            staged = await asyncio.to_thread(
                _stage_file,
                asset.file,
                asset.filename or "asset",
                asset.content_type or "application/octet-stream",
                max_bytes,
            )
            return staged, payload
    except Exception:
        if staged:
            staged.path.unlink(missing_ok=True)
        raise


def _stage_file(
    source: BinaryIO, filename: str, declared_mime: str, max_bytes: int
) -> StagedSubmissionFile:
    path: Path | None = None
    size = 0
    digest = sha256()
    try:
        with NamedTemporaryFile(
            prefix="coeus-submission-", suffix=".stage", delete=False
        ) as target:
            path = Path(target.name)
            while chunk := source.read(CHUNK_SIZE):
                size += len(chunk)
                if size > max_bytes:
                    raise AppError(413, "asset_too_large", "Asset exceeds the local upload limit.")
                digest.update(chunk)
                target.write(chunk)
        if size == 0:
            raise AppError(409, "asset_empty", "Product upload cannot be empty.")
        return StagedSubmissionFile(
            path,
            object_key_segment(filename),
            declared_mime,
            size,
            digest.hexdigest(),
        )
    except Exception:
        if path:
            path.unlink(missing_ok=True)
        raise


def _validate_metadata(raw: str) -> ProductSubmissionMetadataRequest:
    if len(raw.encode()) > MAX_METADATA_BYTES:
        raise AppError(422, "product_metadata_invalid", "Product metadata is too large.")
    try:
        data = json.loads(raw)
        return ProductSubmissionMetadataRequest.model_validate(data)
    except (json.JSONDecodeError, ValidationError, ValueError) as exc:
        raise AppError(422, "product_metadata_invalid", "Product metadata is invalid.") from exc


def _metadata(payload: ProductSubmissionMetadataRequest) -> SubmissionMetadata:
    try:
        releasability, caveats = payload.release_markers()
    except ValueError as exc:
        raise AppError(422, "release_markers_unsupported", str(exc)) from exc
    return SubmissionMetadata(
        payload.title,
        payload.summary,
        payload.description,
        payload.product_type,
        payload.source_type,
        payload.owner_team,
        payload.area_or_region,
        payload.classification_level,
        releasability,
        caveats,
        tuple(sorted({item.strip().casefold() for item in payload.tags if item.strip()})),
        frozenset(payload.acg_ids),
        payload.time_period_start,
        payload.time_period_end,
    )
