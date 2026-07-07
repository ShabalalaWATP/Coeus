from dataclasses import dataclass
from datetime import UTC, date, datetime
from uuid import UUID, uuid4

from coeus.core.errors import AppError
from coeus.core.permissions import Permission
from coeus.domain.access import ProductStatus, ProjectWorkspace
from coeus.domain.auth import UserAccount
from coeus.domain.store import (
    StoreAsset,
    StoreProduct,
    StoreProductMetadata,
    object_key_segment,
)
from coeus.domain.tickets import DraftProductAsset, DraftProductVersion, TicketRecord
from coeus.repositories.access import SeedAccessRepository
from coeus.repositories.store import new_store_product_id
from coeus.services.analyst_records import approved_route
from coeus.services.object_storage import LocalObjectStorage
from coeus.services.qc_acg_policy import validate_qc_acg_assignment
from coeus.services.qc_records import preview_kind
from coeus.services.store import StoreServices
from coeus.services.store_semantics import derive_semantic_labels


@dataclass(frozen=True)
class QcApprovalInput:
    checklist: dict[str, bool]
    classification_level: int
    releasability: tuple[str, ...]
    handling_caveats: tuple[str, ...]
    acg_ids: frozenset[UUID]
    reason: str


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
        access_repository: SeedAccessRepository,
        storage: LocalObjectStorage,
    ) -> None:
        self._store = store
        self._access = access_repository
        self._storage = storage

    def ingest(
        self, actor: UserAccount, ticket: TicketRecord, approval: QcApprovalInput
    ) -> StoreProduct:
        self._require(actor, Permission.PRODUCT_CREATE_FROM_QC)
        draft = latest_draft(ticket)
        project = self._project_for_ticket(ticket)
        project_acg_ids: frozenset[UUID] = project.acg_ids if project else frozenset()
        validate_qc_acg_assignment(self._access, actor, approval.acg_ids, project_acg_ids)
        acg_ids = approval.acg_ids | project_acg_ids
        now = datetime.now(UTC)
        semantic_labels = derive_semantic_labels(
            draft.title,
            draft.summary,
            draft.product_type,
            draft.content,
            ticket.intake.area_or_region or "",
            ticket.intake.required_output_format or "",
        )
        product = StoreProduct(
            product_id=new_store_product_id(),
            reference=self._store.repository.next_reference(),
            metadata=StoreProductMetadata(
                title=draft.title,
                summary=draft.summary,
                description=draft.content,
                product_type=draft.product_type,
                source_type="qc_approved_draft",
                owner_team=_owner_team(ticket),
                area_or_region=ticket.intake.area_or_region or "Not specified",
                classification_level=approval.classification_level,
                releasability=frozenset(approval.releasability),
                handling_caveats=frozenset(approval.handling_caveats),
                tags=frozenset({"mock", "qc-approved", ticket.reference.casefold()}),
                semantic_labels=semantic_labels,
                acg_ids=acg_ids,
                project_id=project.project_id if project else None,
                # Held as draft until the owning manager performs final release.
                status=ProductStatus.DRAFT,
                time_period_start=iso_date_or_none(ticket.intake.time_period_start),
                time_period_end=iso_date_or_none(ticket.intake.time_period_end),
                geojson_ref=None,
                bounding_box=None,
            ),
            assets=tuple(_store_asset(ticket.ticket_id, asset) for asset in draft.assets),
            created_by_user_id=actor.user_id,
            created_at=now,
            updated_at=now,
        )
        if not product.assets:
            raise AppError(409, "asset_required", "Approved products must include an asset.")
        # Write bytes before the product record so a released product is never
        # visible without downloadable content.
        for asset in product.assets:
            self._storage.write_bytes(asset.object_key, _placeholder_content(product, asset))
        self._store.repository.save_product(product)
        return product

    def discard(self, product_id: UUID) -> None:
        """Roll back an ingested product after a downstream failure."""
        self._store.repository.delete_product(product_id)

    def _project_for_ticket(self, ticket: TicketRecord) -> ProjectWorkspace | None:
        for project in self._access.list_projects():
            if ticket.ticket_id in project.ticket_ids:
                return project
        return None

    @staticmethod
    def _require(actor: UserAccount, permission: Permission) -> None:
        if permission not in actor.permissions:
            raise AppError(403, "forbidden", "Permission denied.")


def _store_asset(ticket_id: UUID, asset: DraftProductAsset) -> StoreAsset:
    # The store asset gets its own identity; the object key embeds that same
    # identity so the stored bytes always correspond to the served asset.
    asset_id = uuid4()
    return StoreAsset(
        asset_id=asset_id,
        name=asset.name,
        asset_type=asset.asset_type,
        mime_type=asset.mime_type,
        size_bytes=asset.size_bytes,
        sha256=asset.sha256,
        object_key=f"store/qc/{ticket_id}/{asset_id}/{object_key_segment(asset.name)}",
        preview_kind=preview_kind(asset.mime_type, asset.asset_type),
    )


def _placeholder_content(product: StoreProduct, asset: StoreAsset) -> bytes:
    return (
        "MOCK DATA ONLY\n"
        f"{product.reference}\n"
        f"{product.metadata.title}\n"
        f"{asset.name}\n"
        f"sha256:{asset.sha256}\n"
    ).encode()


def _owner_team(ticket: TicketRecord) -> str:
    route = approved_route(ticket)
    if route is None:
        return "RFA"
    return "Collection" if route.value == "cm" else "RFA"
