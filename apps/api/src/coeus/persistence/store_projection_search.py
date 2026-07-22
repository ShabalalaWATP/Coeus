from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

from coeus.core.resource_limits import STORE_SEARCH_STATEMENT_TIMEOUT_MS
from coeus.domain.access import ProductStatus
from coeus.domain.search_relevance import VECTOR_SIMILARITY_FLOOR
from coeus.domain.store import (
    StoreFacets,
    StoreHybridCandidate,
    StoreProduct,
    StoreProductSearchPage,
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
    SEARCH_SUMMARY_SQL,
    VISIBLE_PRODUCT_SQL,
    VISIBLE_PRODUCTS_SQL,
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


def get_visible_products(
    connection: Connection,
    product_ids: frozenset[object],
    scope: StoreVisibilityScope,
) -> tuple[StoreProduct, ...]:
    if not scope.acg_ids or not product_ids:
        return ()
    params = _scope_params(scope) | {
        "product_ids": [str(product_id) for product_id in sorted(product_ids, key=str)]
    }
    product_rows = _mapping_rows(connection.execute(text(VISIBLE_PRODUCTS_SQL), params))
    if not product_rows:
        return ()
    visible_ids = [str(row["product_id"]) for row in product_rows]
    child_params = {"product_ids": visible_ids}
    asset_rows = _mapping_rows(connection.execute(text(SEARCH_ASSETS_SQL), child_params))
    acg_rows = _mapping_rows(connection.execute(text(SEARCH_ACGS_SQL), child_params))
    label_rows = _mapping_rows(connection.execute(text(SEARCH_LABELS_SQL), child_params))
    return tuple(_decode_product(row, asset_rows, acg_rows, label_rows) for row in product_rows)


def search_product_page(
    connection: Connection,
    filters: StoreSearchFilters,
    scope: StoreVisibilityScope,
) -> StoreProductSearchPage:
    if not scope.acg_ids:
        return StoreProductSearchPage((), 0, StoreFacets((), (), ()))
    connection.execute(
        text("SELECT set_config('statement_timeout', :statement_timeout, true)"),
        {"statement_timeout": f"{STORE_SEARCH_STATEMENT_TIMEOUT_MS}ms"},
    )
    params = _search_params(filters, scope) | {
        "page_size": filters.page_size,
        "offset": (filters.page - 1) * filters.page_size,
    }
    summary_rows = _mapping_rows(connection.execute(text(SEARCH_SUMMARY_SQL), params))
    summary = summary_rows[0] if summary_rows else {}
    product_rows = _mapping_rows(connection.execute(text(SEARCH_PRODUCTS_SQL), params))
    if not product_rows:
        return StoreProductSearchPage(
            (),
            int(summary.get("total") or 0),
            _facets_from_summary(summary),
        )
    product_ids = [str(row["product_id"]) for row in product_rows]
    child_params = {"product_ids": product_ids}
    asset_rows = _mapping_rows(connection.execute(text(SEARCH_ASSETS_SQL), child_params))
    acg_rows = _mapping_rows(connection.execute(text(SEARCH_ACGS_SQL), child_params))
    label_rows = _mapping_rows(connection.execute(text(SEARCH_LABELS_SQL), child_params))
    products = tuple(_decode_product(row, asset_rows, acg_rows, label_rows) for row in product_rows)
    return StoreProductSearchPage(
        products,
        int(summary.get("total") or 0),
        _facets_from_summary(summary),
    )


def hybrid_candidates(
    connection: Connection,
    filters: StoreSearchFilters,
    scope: StoreVisibilityScope,
    query: str,
    query_embedding: str | None,
    leg_limit: int = 50,
) -> tuple[StoreHybridCandidate, ...]:
    if not scope.acg_ids:
        return ()
    params = _search_params(filters, scope) | {
        "query": _blank_to_none(query),
        "query_embedding": query_embedding,
        "leg_limit": leg_limit,
        "vector_similarity_floor": VECTOR_SIMILARITY_FLOOR,
    }
    product_rows = _mapping_rows(connection.execute(text(HYBRID_PRODUCTS_SQL), params))
    if not product_rows:
        return ()
    product_ids = [str(row["product_id"]) for row in product_rows]
    child_params = {"product_ids": product_ids}
    asset_rows = _mapping_rows(connection.execute(text(SEARCH_ASSETS_SQL), child_params))
    acg_rows = _mapping_rows(connection.execute(text(SEARCH_ACGS_SQL), child_params))
    label_rows = _mapping_rows(connection.execute(text(SEARCH_LABELS_SQL), child_params))
    # The run is effectively lexical-only when the query never embedded or when
    # no candidate carries an embedding, so the semantic leg contributed nothing.
    has_vector_leg = any(row.get("vector_rank") is not None for row in product_rows)
    lexical_only = query_embedding is None or not has_vector_leg
    return tuple(
        StoreHybridCandidate(
            product=_decode_product(row, asset_rows, acg_rows, label_rows),
            lexical_rank=_optional_int(row.get("lexical_rank")),
            lexical_score=float(row.get("lexical_score") or 0.0),
            vector_rank=_optional_int(row.get("vector_rank")),
            vector_score=float(row.get("vector_score") or 0.0),
            lexical_only=lexical_only,
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
        "date_from": filters.date_from,
        "date_to": filters.date_to,
        "owner_team": _blank_to_none(filters.owner_team),
    }


def _scope_params(scope: StoreVisibilityScope) -> dict[str, object]:
    return {
        "acg_ids": [str(acg_id) for acg_id in sorted(scope.acg_ids, key=str)],
        "clearance_level": scope.clearance_level,
        "include_drafts": scope.include_drafts,
        "draft_creator_user_id": (
            str(scope.draft_creator_user_id) if scope.draft_creator_user_id else None
        ),
        "draft_principal_user_id": (
            str(scope.draft_principal_user_id) if scope.draft_principal_user_id else None
        ),
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


def _facets_from_summary(summary: dict[str, Any]) -> StoreFacets:
    return StoreFacets(
        product_types=tuple(str(value) for value in summary.get("product_types") or ()),
        regions=tuple(str(value) for value in summary.get("regions") or ()),
        tags=tuple(str(value) for value in summary.get("tags") or ()),
    )


def _decode_product(
    row: dict[str, Any],
    asset_rows: tuple[dict[str, Any], ...],
    acg_rows: tuple[dict[str, Any], ...],
    label_rows: tuple[dict[str, Any], ...],
) -> StoreProduct:
    return decode_product(row, asset_rows, acg_rows, label_rows)
