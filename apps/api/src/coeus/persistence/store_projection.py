import json
from collections.abc import Iterable, Mapping
from datetime import date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine, Result

from coeus.domain.access import ProductStatus
from coeus.domain.store import (
    BoundingBox,
    StoreAsset,
    StoreProduct,
    StoreProductMetadata,
    StoreSearchFilters,
    StoreVisibilityScope,
)
from coeus.domain.store_semantics import effective_semantic_labels
from coeus.persistence.relational_schema import ensure_relational_schema
from coeus.persistence.store_projection_sql import (
    DELETE_ACGS_SQL,
    DELETE_ASSETS_SQL,
    DELETE_LABELS_SQL,
    INSERT_ACG_SQL,
    INSERT_ASSET_SQL,
    INSERT_LABEL_SQL,
    SELECT_ACGS_SQL,
    SELECT_ASSETS_SQL,
    SELECT_LABELS_SQL,
    SELECT_PRODUCTS_SQL,
    UPSERT_PRODUCT_SQL,
)


class PostgresStoreProjection:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def list_products(self) -> tuple[StoreProduct, ...]:
        with self._engine.begin() as connection:
            ensure_relational_schema(connection)
            product_rows = _mapping_rows(connection.execute(text(SELECT_PRODUCTS_SQL)))
            asset_rows = _mapping_rows(connection.execute(text(SELECT_ASSETS_SQL)))
            acg_rows = _mapping_rows(connection.execute(text(SELECT_ACGS_SQL)))
            label_rows = _mapping_rows(connection.execute(text(SELECT_LABELS_SQL)))
        return tuple(_decode_product(row, asset_rows, acg_rows, label_rows) for row in product_rows)

    def search_products(
        self, filters: StoreSearchFilters, scope: StoreVisibilityScope
    ) -> tuple[StoreProduct, ...]:
        from coeus.persistence.store_projection_search import search_products

        with self._engine.begin() as connection:
            ensure_relational_schema(connection)
            return search_products(connection, filters, scope)

    def get_visible_product(
        self, product_id: UUID, scope: StoreVisibilityScope
    ) -> StoreProduct | None:
        from coeus.persistence.store_projection_search import get_visible_product

        with self._engine.begin() as connection:
            ensure_relational_schema(connection)
            return get_visible_product(connection, product_id, scope)

    def save_product(self, product: StoreProduct) -> None:
        with self._engine.begin() as connection:
            ensure_relational_schema(connection)
            _save_product(connection, product)

    def save_products(self, products: tuple[StoreProduct, ...]) -> None:
        with self._engine.begin() as connection:
            ensure_relational_schema(connection)
            _delete_stale_products(connection, products)
            for product in products:
                _save_product(connection, product)


def _mapping_rows(result: Result[Any]) -> tuple[dict[str, Any], ...]:
    return tuple(dict(row) for row in result.mappings())


def _save_product(connection: Connection, product: StoreProduct) -> None:
    connection.execute(text(UPSERT_PRODUCT_SQL), _product_params(product))
    _replace_product_children(
        connection,
        DELETE_ASSETS_SQL,
        product.product_id,
        _asset_params(product),
        INSERT_ASSET_SQL,
    )
    _replace_product_children(
        connection,
        DELETE_ACGS_SQL,
        product.product_id,
        _acg_params(product),
        INSERT_ACG_SQL,
    )
    _replace_product_children(
        connection,
        DELETE_LABELS_SQL,
        product.product_id,
        _label_params(product),
        INSERT_LABEL_SQL,
    )


def _delete_stale_products(connection: Connection, products: tuple[StoreProduct, ...]) -> None:
    if not products:
        connection.execute(text("DELETE FROM intelligence_store_products"))
        return
    connection.execute(
        text(
            """
            DELETE FROM intelligence_store_products
            WHERE NOT (product_id = ANY(CAST(:product_ids AS uuid[])))
            """
        ),
        {"product_ids": [str(product.product_id) for product in products]},
    )


def _replace_product_children(
    connection: Connection,
    delete_sql: str,
    product_id: UUID,
    rows: tuple[dict[str, object], ...],
    insert_sql: str,
) -> None:
    connection.execute(text(delete_sql), {"product_id": str(product_id)})
    for row in rows:
        connection.execute(text(insert_sql), row)


def _product_params(product: StoreProduct) -> dict[str, object]:
    metadata = product.metadata
    return {
        "product_id": str(product.product_id),
        "reference": product.reference,
        "title": metadata.title,
        "summary": metadata.summary,
        "description": metadata.description,
        "product_type": metadata.product_type,
        "source_type": metadata.source_type,
        "owner_team": metadata.owner_team,
        "area_or_region": metadata.area_or_region,
        "classification_level": metadata.classification_level,
        "releasability": sorted(metadata.releasability),
        "handling_caveats": sorted(metadata.handling_caveats),
        "tags": sorted(metadata.tags),
        "semantic_labels": sorted(effective_semantic_labels(product)),
        "acg_ids": [str(acg_id) for acg_id in sorted(metadata.acg_ids, key=str)],
        "project_id": str(metadata.project_id) if metadata.project_id else None,
        "status": metadata.status.value,
        "time_period_start": metadata.time_period_start,
        "time_period_end": metadata.time_period_end,
        "geojson_ref": metadata.geojson_ref,
        "bounding_box": _encode_bounding_box(metadata.bounding_box),
        "created_by_user_id": str(product.created_by_user_id),
        "created_at": product.created_at,
        "updated_at": product.updated_at,
    }


def _asset_params(product: StoreProduct) -> tuple[dict[str, object], ...]:
    return tuple(
        {
            "asset_id": str(asset.asset_id),
            "product_id": str(product.product_id),
            "name": asset.name,
            "asset_type": asset.asset_type,
            "mime_type": asset.mime_type,
            "size_bytes": asset.size_bytes,
            "sha256": asset.sha256,
            "object_key": asset.object_key,
            "preview_kind": asset.preview_kind,
        }
        for asset in product.assets
    )


def _acg_params(product: StoreProduct) -> tuple[dict[str, object], ...]:
    return tuple(
        {"product_id": str(product.product_id), "acg_id": str(acg_id)}
        for acg_id in sorted(product.metadata.acg_ids, key=str)
    )


def _label_params(product: StoreProduct) -> tuple[dict[str, object], ...]:
    return tuple(
        {"product_id": str(product.product_id), "label": label}
        for label in sorted(effective_semantic_labels(product))
    )


def _decode_product(
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


def _encode_bounding_box(bounding_box: BoundingBox | None) -> str | None:
    if bounding_box is None:
        return None
    return json.dumps(
        {
            "west": bounding_box.west,
            "south": bounding_box.south,
            "east": bounding_box.east,
            "north": bounding_box.north,
        }
    )


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
