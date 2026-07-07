import json
from collections.abc import Iterable, Mapping
from datetime import date, datetime
from typing import Any
from uuid import UUID

from coeus.domain.access import ProductStatus
from coeus.domain.store import (
    BoundingBox,
    StoreAsset,
    StoreProduct,
    StoreProductMetadata,
)


def decode_product(
    row: Mapping[str, Any],
    asset_rows: tuple[Mapping[str, Any], ...],
    acg_rows: tuple[Mapping[str, Any], ...],
    label_rows: tuple[Mapping[str, Any], ...],
) -> StoreProduct:
    product_id = _uuid(row["product_id"])
    return StoreProduct(
        product_id=product_id,
        reference=str(row["reference"]),
        metadata=StoreProductMetadata(
            title=str(row["title"]),
            summary=str(row["summary"]),
            description=str(row["description"]),
            product_type=str(row["product_type"]),
            source_type=str(row["source_type"]),
            owner_team=str(row["owner_team"]),
            area_or_region=str(row["area_or_region"]),
            classification_level=int(row["classification_level"]),
            releasability=_text_set(row["releasability"]),
            handling_caveats=_text_set(row["handling_caveats"]),
            tags=_text_set(row["tags"]),
            semantic_labels=_semantic_labels(product_id, row, label_rows),
            acg_ids=_acg_ids(product_id, row, acg_rows),
            project_id=_optional_uuid(row["project_id"]),
            status=ProductStatus(str(row["status"])),
            time_period_start=_date_text(row["time_period_start"]),
            time_period_end=_date_text(row["time_period_end"]),
            geojson_ref=_optional_text(row["geojson_ref"]),
            bounding_box=_decode_bounding_box(row["bounding_box"]),
        ),
        assets=_assets(product_id, asset_rows),
        created_by_user_id=_uuid(row["created_by_user_id"]),
        created_at=_datetime(row["created_at"]),
        updated_at=_datetime(row["updated_at"]),
    )


def _assets(product_id: UUID, rows: tuple[Mapping[str, Any], ...]) -> tuple[StoreAsset, ...]:
    return tuple(
        StoreAsset(
            asset_id=_uuid(row["asset_id"]),
            name=str(row["name"]),
            asset_type=str(row["asset_type"]),
            mime_type=str(row["mime_type"]),
            size_bytes=int(row["size_bytes"]),
            sha256=str(row["sha256"]),
            object_key=str(row["object_key"]),
            preview_kind=str(row["preview_kind"]),
        )
        for row in rows
        if _uuid(row["product_id"]) == product_id
    )


def _acg_ids(
    product_id: UUID, row: Mapping[str, Any], rows: tuple[Mapping[str, Any], ...]
) -> frozenset[UUID]:
    joined = frozenset(
        _uuid(acg_row["acg_id"]) for acg_row in rows if _uuid(acg_row["product_id"]) == product_id
    )
    return joined or _uuid_set(row["acg_ids"])


def _semantic_labels(
    product_id: UUID, row: Mapping[str, Any], rows: tuple[Mapping[str, Any], ...]
) -> frozenset[str]:
    joined = frozenset(
        str(label_row["label"])
        for label_row in rows
        if _uuid(label_row["product_id"]) == product_id
    )
    return joined or _text_set(row["semantic_labels"])


def _decode_bounding_box(value: object) -> BoundingBox | None:
    if value is None:
        return None
    data = json.loads(value) if isinstance(value, str) else value
    if not isinstance(data, Mapping):
        return None
    return BoundingBox(
        west=float(data["west"]),
        south=float(data["south"]),
        east=float(data["east"]),
        north=float(data["north"]),
    )


def _text_set(values: object) -> frozenset[str]:
    return frozenset(str(value) for value in _iter_values(values))


def _uuid_set(values: object) -> frozenset[UUID]:
    return frozenset(_uuid(value) for value in _iter_values(values))


def _iter_values(values: object) -> tuple[object, ...]:
    if values is None:
        return ()
    if isinstance(values, str | bytes):
        return (values,)
    if isinstance(values, Iterable):
        return tuple(values)
    return (values,)


def _uuid(value: object) -> UUID:
    return value if isinstance(value, UUID) else UUID(str(value))


def _optional_uuid(value: object) -> UUID | None:
    return None if value is None else _uuid(value)


def _optional_text(value: object) -> str | None:
    return None if value is None else str(value)


def _date_text(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _datetime(value: object) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value))
