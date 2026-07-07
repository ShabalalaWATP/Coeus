from dataclasses import dataclass
from datetime import UTC, datetime
from re import fullmatch
from uuid import UUID, uuid4

from coeus.core.errors import AppError
from coeus.domain.tickets import DraftProductAsset

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
