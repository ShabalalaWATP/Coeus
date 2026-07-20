from dataclasses import dataclass
from datetime import UTC, date, datetime
from hashlib import sha256
from uuid import UUID, uuid4

from coeus.core.errors import AppError
from coeus.core.permissions import Permission
from coeus.domain.access import ProductStatus
from coeus.domain.auth import UserAccount
from coeus.domain.store import (
    StoreAsset,
    StoreProduct,
    StoreProductMetadata,
    object_key_segment,
)
from coeus.domain.tickets import DraftProductAsset, DraftProductVersion, TicketRecord
from coeus.repositories.access import AccessRepository
from coeus.repositories.store_ids import new_store_product_id
from coeus.services.analyst_records import approved_route
from coeus.services.object_storage import ObjectStorage
from coeus.services.qc_acg_policy import validate_qc_acg_assignment
from coeus.services.qc_records import preview_kind
from coeus.services.store import StoreServices
from coeus.services.store_semantics import derive_semantic_labels
from coeus.services.workflow_draft_access import WorkflowDraftAccessPolicy


@dataclass(frozen=True)
class QcApprovalInput:
    checklist: dict[str, bool]
    classification_level: int
    releasability: tuple[str, ...]
    handling_caveats: tuple[str, ...]
    acg_ids: frozenset[UUID]
    reason: str


@dataclass(frozen=True)
class PreparedAsset:
    asset: StoreAsset
    content: bytes


def iso_date_or_none(value: str | None) -> str | None:
    """Return the value only when it is a valid ISO calendar date.

    Intake time periods are free text; the store projection stores real dates,
    so anything unparsable is dropped rather than crashing mid-approval.
    """
    if value is None:
        return None
    try:
        date.fromisoformat(value)
    except ValueError:
        return None
    return value


def latest_draft(ticket: TicketRecord) -> DraftProductVersion:
    if not ticket.draft_products:
        raise AppError(409, "draft_required", "A draft product is required before QC.")
    return ticket.draft_products[-1]


class ProductAutoIngestionService:
    def __init__(
        self,
        store: StoreServices,
        access_repository: AccessRepository,
        storage: ObjectStorage,
        draft_access: WorkflowDraftAccessPolicy,
    ) -> None:
        self._store = store
        self._access = access_repository
        self._storage = storage
        self._draft_access = draft_access

    def ingest(
        self, actor: UserAccount, ticket: TicketRecord, approval: QcApprovalInput
    ) -> StoreProduct:
        self._require(actor, Permission.PRODUCT_CREATE_FROM_QC)
        draft = latest_draft(ticket)
        self._draft_access.require_version(actor, ticket, draft)
        validate_qc_acg_assignment(self._access, actor, approval.acg_ids, frozenset())
        now = datetime.now(UTC)
        semantic_labels = derive_semantic_labels(
            draft.title,
            draft.summary,
            draft.product_type,
            draft.content,
            draft.area_or_region or ticket.intake.area_or_region or "",
            ticket.intake.required_output_format or "",
        )
        reference = self._store.repository.next_reference()
        prepared_assets = tuple(
            _prepare_asset(ticket.ticket_id, reference, draft.title, asset, self._storage)
            for asset in draft.assets
        )
        product = StoreProduct(
            product_id=new_store_product_id(),
            reference=reference,
            metadata=StoreProductMetadata(
                title=draft.title,
                summary=draft.summary,
                description=draft.description or draft.content,
                product_type=draft.product_type,
                source_type=draft.source_type or "qc_approved_submission",
                owner_team=draft.owner_team or _owner_team(ticket),
                area_or_region=(
                    draft.area_or_region or ticket.intake.area_or_region or "Not specified"
                ),
                classification_level=approval.classification_level,
                releasability=frozenset(approval.releasability),
                handling_caveats=frozenset(approval.handling_caveats),
                tags=frozenset({"mock", "qc-approved", ticket.reference.casefold(), *draft.tags}),
                semantic_labels=semantic_labels,
                acg_ids=approval.acg_ids,
                # Held as draft until the owning manager performs final release.
                status=ProductStatus.DRAFT,
                time_period_start=iso_date_or_none(
                    draft.time_period_start or ticket.intake.time_period_start
                ),
                time_period_end=iso_date_or_none(
                    draft.time_period_end or ticket.intake.time_period_end
                ),
                geojson_ref=None,
                bounding_box=None,
            ),
            assets=tuple(prepared.asset for prepared in prepared_assets),
            created_by_user_id=actor.user_id,
            created_at=now,
            updated_at=now,
        )
        if not product.assets:
            raise AppError(409, "asset_required", "Approved products must include an asset.")
        # Write bytes before the product record so a released product is never
        # visible without downloadable content.
        written_keys: list[str] = []
        try:
            for prepared in prepared_assets:
                written_keys.append(prepared.asset.object_key)
                self._storage.write_bytes(prepared.asset.object_key, prepared.content)
            self._store.repository.save_product(product)
        except Exception:
            for object_key in reversed(written_keys):
                self._storage.delete_bytes(object_key)
            raise
        return product

    def discard(self, product_id: UUID) -> None:
        """Roll back an ingested product after a downstream failure."""
        product = self._store.repository.get_product(product_id)
        if product is not None:
            for asset in product.assets:
                self._storage.delete_bytes(asset.object_key)
        self._store.repository.delete_product(product_id)

    @staticmethod
    def _require(actor: UserAccount, permission: Permission) -> None:
        if permission not in actor.permissions:
            raise AppError(403, "forbidden", "Permission denied.")


def _prepare_asset(
    ticket_id: UUID,
    reference: str,
    product_title: str,
    asset: DraftProductAsset,
    storage: ObjectStorage,
) -> PreparedAsset:
    # The store asset gets its own identity; the object key embeds that same
    # identity so the stored bytes always correspond to the served asset.
    asset_id = uuid4()
    object_key = f"store/qc/{ticket_id}/{asset_id}/{object_key_segment(asset.name)}"
    content = _source_content(storage, asset, reference, product_title)
    store_asset = StoreAsset(
        asset_id=asset_id,
        name=asset.name,
        asset_type=asset.asset_type,
        mime_type=asset.detected_mime_type or asset.mime_type,
        size_bytes=len(content),
        sha256=sha256(content).hexdigest(),
        object_key=object_key,
        preview_kind=(asset.preview_kind or preview_kind(asset.mime_type, asset.asset_type)),
    )
    return PreparedAsset(store_asset, content)


def _placeholder_content(reference: str, product_title: str, asset_name: str) -> bytes:
    return (f"MOCK DATA ONLY\n{reference}\n{product_title}\n{asset_name}\n").encode()


def _source_content(
    storage: ObjectStorage,
    asset: DraftProductAsset,
    reference: str,
    product_title: str,
) -> bytes:
    # Metadata-only versions are retained solely for old synthetic fixtures.
    if not asset.object_key:
        return _placeholder_content(reference, product_title, asset.name)
    if not storage.exists(asset.object_key):
        raise AppError(409, "submission_asset_missing", "Approved source asset is unavailable.")
    content = storage.read_bytes(asset.object_key)
    if len(content) != asset.size_bytes or sha256(content).hexdigest() != asset.sha256:
        raise AppError(409, "submission_asset_integrity_failed", "Approved source asset changed.")
    return content


def _owner_team(ticket: TicketRecord) -> str:
    route = approved_route(ticket)
    if route is None:
        return "RFA"
    return "Collection" if route.value == "cm" else "RFA"
