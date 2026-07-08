from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

from coeus.domain.access import ProductStatus
from coeus.domain.store import (
    StoreHybridCandidate,
    StoreProduct,
    StoreSearchFilters,
    StoreVisibilityScope,
)
from coeus.persistence.store_projection_decode import decode_product
from coeus.persistence.store_projection_search_sql import (
    HYBRID_PRODUCTS_SQL,
    SEARCH_ACGS_SQL,
    SEARCH_ASSETS_SQL,
    SEARCH_LABELS_SQL,
    SEARCH_PRODUCTS_SQL,
    VISIBLE_PRODUCT_SQL,
)


def get_visible_product(
    connection: Connection,
    product_id: object,
    scope: StoreVisibilityScope,
) -> StoreProduct | None:
    if not scope.acg_ids:
        return None
    params = _scope_params(scope) | {"product_id": str(product_id)}
    product_rows = _mapping_rows(connection.execute(text(VISIBLE_PRODUCT_SQL), params))
    if not product_rows:
        return None
    child_params = {"product_ids": [str(product_rows[0]["product_id"])]}
    asset_rows = _mapping_rows(connection.execute(text(SEARCH_ASSETS_SQL), child_params))
    acg_rows = _mapping_rows(connection.execute(text(SEARCH_ACGS_SQL), child_params))
    label_rows = _mapping_rows(connection.execute(text(SEARCH_LABELS_SQL), child_params))
    return _decode_product(product_rows[0], asset_rows, acg_rows, label_rows)


def search_products(
    connection: Connection,
    filters: StoreSearchFilters,
    scope: StoreVisibilityScope,
) -> tuple[StoreProduct, ...]:
    if not scope.acg_ids:
        return ()
    params = _search_params(filters, scope)
    product_rows = _mapping_rows(connection.execute(text(SEARCH_PRODUCTS_SQL), params))
    if not product_rows:
        return ()
    product_ids = [str(row["product_id"]) for row in product_rows]
    child_params = {"product_ids": product_ids}
    asset_rows = _mapping_rows(connection.execute(text(SEARCH_ASSETS_SQL), child_params))
    acg_rows = _mapping_rows(connection.execute(text(SEARCH_ACGS_SQL), child_params))
    label_rows = _mapping_rows(connection.execute(text(SEARCH_LABELS_SQL), child_params))
    return tuple(_decode_product(row, asset_rows, acg_rows, label_rows) for row in product_rows)


def hybrid_candidates(
    connection: Connection,
    filters: StoreSearchFilters,
    scope: StoreVisibilityScope,
    query: str,
    query_embedding: str | None,
) -> tuple[StoreHybridCandidate, ...]:
    if not scope.acg_ids:
        return ()
    params = _search_params(filters, scope) | {
        "query": _blank_to_none(query),
        "query_embedding": query_embedding,
        "leg_limit": 50,
    }
    product_rows = _mapping_rows(connection.execute(text(HYBRID_PRODUCTS_SQL), params))
    if not product_rows:
        return ()
    product_ids = [str(row["product_id"]) for row in product_rows]
    child_params = {"product_ids": product_ids}
    asset_rows = _mapping_rows(connection.execute(text(SEARCH_ASSETS_SQL), child_params))
    acg_rows = _mapping_rows(connection.execute(text(SEARCH_ACGS_SQL), child_params))
    label_rows = _mapping_rows(connection.execute(text(SEARCH_LABELS_SQL), child_params))
    return tuple(
        StoreHybridCandidate(
            product=_decode_product(row, asset_rows, acg_rows, label_rows),
            lexical_rank=_optional_int(row.get("lexical_rank")),
            lexical_score=float(row.get("lexical_score") or 0.0),
            vector_rank=_optional_int(row.get("vector_rank")),
            vector_score=float(row.get("vector_score") or 0.0),
            lexical_only=query_embedding is None,
        )
        for row in product_rows
    )


def _search_params(filters: StoreSearchFilters, scope: StoreVisibilityScope) -> dict[str, object]:
    query = _blank_to_none(filters.query)
    return _scope_params(scope) | {
        "query": query,
        "query_like": _escape_like(query),
        "product_type": filters.product_type,
        "region": _escape_like(_blank_to_none(filters.region)),
        "tag": _blank_to_none(filters.tag),
        "source_type": filters.source_type,
        "status": filters.status.value if filters.status else None,
        "project_id": str(filters.project_id) if filters.project_id else None,
        "date_from": filters.date_from,
        "date_to": filters.date_to,
        "owner_team": _blank_to_none(filters.owner_team),
    }


def _scope_params(scope: StoreVisibilityScope) -> dict[str, object]:
    return {
        "acg_ids": [str(acg_id) for acg_id in sorted(scope.acg_ids, key=str)],
        "clearance_level": scope.clearance_level,
        "include_drafts": scope.include_drafts,
        "archived_status": ProductStatus.ARCHIVED.value,
        "draft_status": ProductStatus.DRAFT.value,
    }


def _blank_to_none(value: str | None) -> str | None:
    if value is None or value.strip() == "":
        return None
    return value.strip()


def _escape_like(value: str | None) -> str | None:
    """Escape user input used in ILIKE patterns so wildcards match literally."""
    if value is None:
        return None
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _mapping_rows(result: Any) -> tuple[dict[str, Any], ...]:
    return tuple(dict(row) for row in result.mappings())


def _optional_int(value: object) -> int | None:
    return None if value is None else int(str(value))


def _decode_product(
    row: dict[str, Any],
    asset_rows: tuple[dict[str, Any], ...],
    acg_rows: tuple[dict[str, Any], ...],
    label_rows: tuple[dict[str, Any], ...],
) -> StoreProduct:
    return decode_product(row, asset_rows, acg_rows, label_rows)
