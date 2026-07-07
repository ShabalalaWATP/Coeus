from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

from coeus.domain.access import ProductStatus
from coeus.domain.store import StoreProduct, StoreSearchFilters, StoreVisibilityScope
from coeus.persistence.store_projection_decode import decode_product


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


def _decode_product(
    row: dict[str, Any],
    asset_rows: tuple[dict[str, Any], ...],
    acg_rows: tuple[dict[str, Any], ...],
    label_rows: tuple[dict[str, Any], ...],
) -> StoreProduct:
    return decode_product(row, asset_rows, acg_rows, label_rows)


VISIBLE_PRODUCT_SQL = """
SELECT
    p.product_id,
    p.reference,
    p.title,
    p.summary,
    p.description,
    p.product_type,
    p.source_type,
    p.owner_team,
    p.area_or_region,
    p.classification_level,
    p.releasability,
    p.handling_caveats,
    p.tags,
    p.semantic_labels,
    p.acg_ids,
    p.project_id,
    p.status,
    p.time_period_start,
    p.time_period_end,
    p.geojson_ref,
    p.bounding_box,
    p.created_by_user_id,
    p.created_at,
    p.updated_at
FROM intelligence_store_products p
WHERE p.product_id = CAST(:product_id AS uuid)
  AND p.status <> :archived_status
  AND p.classification_level <= :clearance_level
  AND (:include_drafts OR p.status <> :draft_status)
  AND EXISTS (
      SELECT 1
      FROM intelligence_store_product_acgs product_acg
      WHERE product_acg.product_id = p.product_id
        AND product_acg.acg_id = ANY(CAST(:acg_ids AS uuid[]))
  )
"""


SEARCH_PRODUCTS_SQL = """
SELECT
    p.product_id,
    p.reference,
    p.title,
    p.summary,
    p.description,
    p.product_type,
    p.source_type,
    p.owner_team,
    p.area_or_region,
    p.classification_level,
    p.releasability,
    p.handling_caveats,
    p.tags,
    p.semantic_labels,
    p.acg_ids,
    p.project_id,
    p.status,
    p.time_period_start,
    p.time_period_end,
    p.geojson_ref,
    p.bounding_box,
    p.created_by_user_id,
    p.created_at,
    p.updated_at
FROM intelligence_store_products p
WHERE p.status <> :archived_status
  AND p.classification_level <= :clearance_level
  AND (:include_drafts OR p.status <> :draft_status)
  AND EXISTS (
      SELECT 1
      FROM intelligence_store_product_acgs product_acg
      WHERE product_acg.product_id = p.product_id
        AND product_acg.acg_id = ANY(CAST(:acg_ids AS uuid[]))
  )
  AND (CAST(:product_type AS text) IS NULL OR p.product_type = CAST(:product_type AS text))
  AND (CAST(:source_type AS text) IS NULL OR p.source_type = CAST(:source_type AS text))
  AND (CAST(:status AS text) IS NULL OR p.status = CAST(:status AS text))
  AND (CAST(:project_id AS uuid) IS NULL OR p.project_id = CAST(:project_id AS uuid))
  AND (
      CAST(:owner_team AS text) IS NULL
      OR lower(p.owner_team) = lower(CAST(:owner_team AS text))
  )
  AND (
      CAST(:region AS text) IS NULL
      OR p.area_or_region ILIKE '%' || CAST(:region AS text) || '%' ESCAPE '\\'
  )
  AND (
      CAST(:tag AS text) IS NULL
      OR lower(CAST(:tag AS text)) = ANY (
          SELECT lower(tag_value)
          FROM unnest(p.tags) AS tag_value
      )
  )
  AND (
      (CAST(:date_from AS date) IS NULL AND CAST(:date_to AS date) IS NULL)
      OR (
          p.time_period_start IS NOT NULL
          AND (CAST(:date_from AS date) IS NULL OR coalesce(p.time_period_end, p.time_period_start)
              >= CAST(:date_from AS date))
          AND (CAST(:date_to AS date) IS NULL OR p.time_period_start <= CAST(:date_to AS date))
      )
  )
  AND (
      CAST(:query AS text) IS NULL
      OR p.search_document @@ websearch_to_tsquery('english', CAST(:query AS text))
      OR concat_ws(
          ' ',
          p.title,
          p.summary,
          p.description,
          p.product_type,
          p.source_type,
          p.owner_team,
          p.area_or_region,
          array_to_string(p.tags, ' '),
          array_to_string(p.semantic_labels, ' ')
      ) ILIKE '%' || CAST(:query_like AS text) || '%' ESCAPE '\\'
  )
ORDER BY p.title ASC
"""

SEARCH_ASSETS_SQL = """
SELECT
    asset_id,
    product_id,
    name,
    asset_type,
    mime_type,
    size_bytes,
    sha256,
    object_key,
    preview_kind
FROM intelligence_store_assets
WHERE product_id = ANY(CAST(:product_ids AS uuid[]))
ORDER BY name ASC
"""

SEARCH_ACGS_SQL = """
SELECT product_id, acg_id
FROM intelligence_store_product_acgs
WHERE product_id = ANY(CAST(:product_ids AS uuid[]))
ORDER BY acg_id ASC
"""

SEARCH_LABELS_SQL = """
SELECT product_id, label
FROM intelligence_store_semantic_labels
WHERE product_id = ANY(CAST(:product_ids AS uuid[]))
ORDER BY label ASC
"""
