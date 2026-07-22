"""Immutable analyst product submission records."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class DraftProductAsset:
    asset_id: UUID
    name: str
    asset_type: str
    mime_type: str
    size_bytes: int
    sha256: str
    detected_mime_type: str = ""
    object_key: str = ""
    preview_kind: str = "metadata"
    processing_status: str = "metadata_only"
    extracted_text: str = ""


@dataclass(frozen=True)
class DraftProductVersion:
    version_id: UUID
    ticket_id: UUID
    version_number: int
    title: str
    summary: str
    product_type: str
    content: str
    assets: tuple[DraftProductAsset, ...]
    created_by_user_id: UUID
    created_at: datetime
    description: str = ""
    source_type: str = ""
    owner_team: str = ""
    area_or_region: str = ""
    classification_level: int = 0
    releasability: tuple[str, ...] = ()
    handling_caveats: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    acg_ids: frozenset[UUID] = frozenset()
    time_period_start: str | None = None
    time_period_end: str | None = None
    manifest_hash: str = ""

    @property
    def has_uploaded_source(self) -> bool:
        return bool(self.assets) and all(
            asset.object_key and asset.processing_status == "ready" for asset in self.assets
        )
