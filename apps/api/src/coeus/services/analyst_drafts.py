from dataclasses import dataclass
from datetime import UTC, datetime
from re import fullmatch
from uuid import UUID, uuid4

from coeus.core.errors import AppError
from coeus.core.resource_limits import (
    MAX_DRAFT_HISTORY_BYTES,
    MAX_DRAFT_VERSIONS,
    text_bytes,
)
from coeus.domain.product_submission import DraftProductAsset, DraftProductVersion

HASH_PATTERN = r"[a-fA-F0-9]{64}"


@dataclass(frozen=True)
class DraftAssetInput:
    name: str
    asset_type: str
    mime_type: str
    size_bytes: int
    sha256: str


@dataclass(frozen=True)
class DraftProductInput:
    title: str
    summary: str
    product_type: str
    content: str
    assets: tuple[DraftAssetInput, ...]


def ensure_draft_budget(
    existing: tuple[DraftProductVersion, ...], incoming: DraftProductInput
) -> None:
    existing_bytes = sum(_stored_draft_bytes(item) for item in existing)
    incoming_bytes = text_bytes(
        incoming.title, incoming.summary, incoming.product_type, incoming.content
    ) + sum(
        text_bytes(asset.name, asset.asset_type, asset.mime_type, asset.sha256)
        for asset in incoming.assets
    )
    if (
        len(existing) >= MAX_DRAFT_VERSIONS
        or existing_bytes + incoming_bytes > MAX_DRAFT_HISTORY_BYTES
    ):
        raise AppError(409, "draft_history_limit_reached", "The draft history limit was reached.")


def _stored_draft_bytes(draft: DraftProductVersion) -> int:
    return text_bytes(draft.title, draft.summary, draft.product_type, draft.content) + sum(
        text_bytes(asset.name, asset.asset_type, asset.mime_type, asset.sha256)
        for asset in draft.assets
    )


def draft_asset(asset: DraftAssetInput) -> DraftProductAsset:
    if not fullmatch(HASH_PATTERN, asset.sha256):
        raise AppError(409, "asset_hash_invalid", "Asset SHA-256 must be 64 hex chars.")
    if asset.size_bytes < 1:
        raise AppError(409, "asset_size_invalid", "Asset size must be positive.")
    return DraftProductAsset(
        asset_id=new_uuid(),
        name=asset.name,
        asset_type=asset.asset_type,
        mime_type=asset.mime_type,
        size_bytes=asset.size_bytes,
        sha256=asset.sha256,
    )


def now() -> datetime:
    return datetime.now(UTC)


def new_uuid() -> UUID:
    return uuid4()
