"""Ticket-scoped ingestion and access for externally authored analyst products."""

from dataclasses import dataclass, replace
from datetime import date
from hashlib import sha256
from pathlib import Path
from uuid import UUID, uuid4

from coeus.core.config import HOSTED_ENVIRONMENTS, Settings
from coeus.core.errors import AppError
from coeus.core.permissions import Permission
from coeus.domain.auth import UserAccount
from coeus.domain.product_submission import DraftProductAsset, DraftProductVersion
from coeus.repositories.access import AccessRepository
from coeus.services.analyst_drafts import DraftAssetInput, DraftProductInput, ensure_draft_budget
from coeus.services.analyst_records import next_draft_version
from coeus.services.analyst_workflow import ACTIVE_ANALYST_STATES, AnalystWorkflowService
from coeus.services.object_storage import ObjectStorage
from coeus.services.product_processing import ProcessedProductFile, process_product_file
from coeus.services.qc_acg_policy import validate_qc_acg_assignment
from coeus.services.ticket_records import timeline
from coeus.services.tickets import TicketServices


@dataclass(frozen=True)
class SubmissionMetadata:
    title: str
    summary: str
    description: str
    product_type: str
    source_type: str
    owner_team: str
    area_or_region: str
    classification_level: int
    releasability: tuple[str, ...]
    handling_caveats: tuple[str, ...]
    tags: tuple[str, ...]
    acg_ids: frozenset[UUID]
    time_period_start: str | None
    time_period_end: str | None


@dataclass(frozen=True)
class StagedSubmissionFile:
    path: Path
    name: str
    declared_mime_type: str
    size_bytes: int
    sha256: str


class ProductSubmissionService:
    def __init__(
        self,
        tickets: TicketServices,
        analyst: AnalystWorkflowService,
        access: AccessRepository,
        storage: ObjectStorage,
        settings: Settings,
    ) -> None:
        self._tickets = tickets
        self._analyst = analyst
        self._access = access
        self._storage = storage
        self._settings = settings

    def authorise_upload(self, actor: UserAccount, ticket_id: UUID) -> None:
        if Permission.ANALYST_SUBMIT_PRODUCT not in actor.permissions:
            raise AppError(403, "forbidden", "Permission denied.")
        ticket = self._analyst.task_details(actor, ticket_id)
        if ticket.state not in ACTIVE_ANALYST_STATES:
            raise AppError(409, "invalid_ticket_state", "Analyst task is not in progress.")

    def create(
        self,
        actor: UserAccount,
        ticket_id: UUID,
        metadata: SubmissionMetadata,
        staged: StagedSubmissionFile,
    ) -> DraftProductVersion:
        self.authorise_upload(actor, ticket_id)
        ticket = self._analyst.task_details(actor, ticket_id)
        validate_qc_acg_assignment(self._access, actor, metadata.acg_ids, frozenset())
        _validate_dates(metadata.time_period_start, metadata.time_period_end)
        processed = process_product_file(
            staged.path,
            staged.name,
            hosted_environment=self._settings.environment in HOSTED_ENVIRONMENTS,
        )
        version_id = uuid4()
        asset_id = uuid4()
        object_key = f"workflow/submissions/{ticket_id}/{version_id}/{asset_id}/{staged.name}"
        asset = _asset(staged, processed, asset_id, object_key)
        content = processed.extracted_text or metadata.description
        ensure_draft_budget(
            ticket.draft_products,
            DraftProductInput(
                metadata.title,
                metadata.summary,
                metadata.product_type,
                content,
                (
                    DraftAssetInput(
                        asset.name,
                        asset.asset_type,
                        asset.mime_type,
                        asset.size_bytes,
                        asset.sha256,
                    ),
                ),
            ),
        )
        version = _version(
            ticket_id,
            next_draft_version(ticket),
            version_id,
            actor.user_id,
            metadata,
            asset,
            content,
        )
        self._storage.write_file(object_key, staged.path)
        try:
            updated = replace(
                ticket,
                draft_products=(*ticket.draft_products, version),
                manager_approved_manifest_hash=None,
                timeline=(
                    *ticket.timeline,
                    timeline(
                        ticket.ticket_id,
                        actor.user_id,
                        "product_submission_uploaded",
                        "An immutable external product version was uploaded for review.",
                    ),
                ),
            )
            self._tickets.mutations.save_audited_if_current(
                ticket,
                updated,
                "product_submission_uploaded",
                actor,
                {
                    "ticket_id": str(ticket_id),
                    "version_id": str(version.version_id),
                    "manifest_hash": version.manifest_hash,
                },
            )
        except Exception:
            self._storage.delete_bytes(object_key)
            raise
        return version


def _asset(
    staged: StagedSubmissionFile,
    processed: ProcessedProductFile,
    asset_id: UUID,
    object_key: str,
) -> DraftProductAsset:
    return DraftProductAsset(
        asset_id=asset_id,
        name=staged.name,
        asset_type=processed.asset_type,
        mime_type=processed.detected_mime_type,
        size_bytes=staged.size_bytes,
        sha256=staged.sha256,
        detected_mime_type=processed.detected_mime_type,
        object_key=object_key,
        preview_kind=processed.preview_kind,
        processing_status="ready",
        extracted_text=processed.extracted_text,
    )


def _version(
    ticket_id: UUID,
    number: int,
    version_id: UUID,
    actor_id: UUID,
    metadata: SubmissionMetadata,
    asset: DraftProductAsset,
    content: str,
) -> DraftProductVersion:
    manifest = _manifest_hash(metadata, asset)
    from datetime import UTC, datetime

    return DraftProductVersion(
        version_id=version_id,
        ticket_id=ticket_id,
        version_number=number,
        title=metadata.title,
        summary=metadata.summary,
        product_type=metadata.product_type,
        content=content,
        assets=(asset,),
        created_by_user_id=actor_id,
        created_at=datetime.now(UTC),
        description=metadata.description,
        source_type=metadata.source_type,
        owner_team=metadata.owner_team,
        area_or_region=metadata.area_or_region,
        classification_level=metadata.classification_level,
        releasability=metadata.releasability,
        handling_caveats=metadata.handling_caveats,
        tags=metadata.tags,
        acg_ids=metadata.acg_ids,
        time_period_start=metadata.time_period_start,
        time_period_end=metadata.time_period_end,
        manifest_hash=manifest,
    )


def _manifest_hash(metadata: SubmissionMetadata, asset: DraftProductAsset) -> str:
    values = (
        metadata.title,
        metadata.summary,
        metadata.description,
        metadata.product_type,
        metadata.source_type,
        metadata.owner_team,
        metadata.area_or_region,
        str(metadata.classification_level),
        *sorted(metadata.releasability),
        *sorted(metadata.handling_caveats),
        *sorted(metadata.tags),
        *(str(item) for item in sorted(metadata.acg_ids, key=str)),
        metadata.time_period_start or "",
        metadata.time_period_end or "",
        asset.sha256,
        str(asset.size_bytes),
        asset.detected_mime_type,
    )
    return sha256("\u241f".join(values).encode()).hexdigest()


def _validate_dates(start: str | None, end: str | None) -> None:
    try:
        parsed_start = date.fromisoformat(start) if start else None
        parsed_end = date.fromisoformat(end) if end else None
    except ValueError as exc:
        raise AppError(422, "product_dates_invalid", "Product dates must use YYYY-MM-DD.") from exc
    if parsed_start and parsed_end and parsed_start > parsed_end:
        raise AppError(422, "product_dates_invalid", "Product start date must precede end date.")
