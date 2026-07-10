import json
from collections.abc import Mapping
from hashlib import sha256
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Connection

from coeus.domain.store import BoundingBox, StoreProduct
from coeus.domain.store_semantics import effective_semantic_labels
from coeus.persistence.store_projection_sql import (
    DELETE_ACGS_SQL,
    DELETE_ASSETS_SQL,
    DELETE_LABELS_SQL,
    INSERT_ACG_SQL,
    INSERT_ASSET_SQL,
    INSERT_LABEL_SQL,
    SELECT_EMBEDDING_HASHES_SQL,
    UPSERT_PRODUCT_SQL,
)
from coeus.services.embeddings import EmbeddingService, vector_to_pg
from coeus.services.store_semantics import product_semantic_text


def save_product(
    connection: Connection,
    product: StoreProduct,
    embeddings: EmbeddingService | None = None,
    existing_hashes: Mapping[str, str | None] | None = None,
) -> None:
    connection.execute(
        text(UPSERT_PRODUCT_SQL),
        _product_params(product, embeddings, existing_hashes or {}),
    )
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


def delete_stale_products(connection: Connection, products: tuple[StoreProduct, ...]) -> None:
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


def existing_embedding_hashes(
    connection: Connection, product_ids: tuple[UUID, ...]
) -> dict[str, str | None]:
    if not product_ids:
        return {}
    result = connection.execute(
        text(SELECT_EMBEDDING_HASHES_SQL),
        {"product_ids": [str(product_id) for product_id in product_ids]},
    )
    return {
        str(row["product_id"]): (
            None if row["embedding_source_hash"] is None else str(row["embedding_source_hash"])
        )
        for row in result.mappings()
    }


def semantic_hash(semantic_text: str) -> str:
    return sha256(semantic_text.encode("utf-8")).hexdigest()


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


def _product_params(
    product: StoreProduct,
    embeddings: EmbeddingService | None = None,
    existing_hashes: Mapping[str, str | None] | None = None,
) -> dict[str, object]:
    metadata = product.metadata
    hashes = existing_hashes or {}
    semantic_text = product_semantic_text(product)
    source_hash = semantic_hash(semantic_text)
    embedding: tuple[float, ...] | None = None
    stored_hash: str | None = None
    if embeddings is not None and hashes.get(str(product.product_id)) != source_hash:
        embedding = embeddings.embed(semantic_text, purpose="store-product-write")
        stored_hash = source_hash if embedding is not None else None
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
        "status": metadata.status.value,
        "time_period_start": metadata.time_period_start,
        "time_period_end": metadata.time_period_end,
        "geojson_ref": metadata.geojson_ref,
        "bounding_box": _encode_bounding_box(metadata.bounding_box),
        "created_by_user_id": str(product.created_by_user_id),
        "created_at": product.created_at,
        "updated_at": product.updated_at,
        "embedding": vector_to_pg(embedding),
        "embedding_source_hash": stored_hash,
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
