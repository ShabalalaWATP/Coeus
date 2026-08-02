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
  AND p.releasability = ARRAY['MOCK']::text[]
  AND p.handling_caveats = ARRAY['MOCK DATA ONLY']::text[]
  AND (
      :include_drafts
      OR p.status <> :draft_status
      OR p.created_by_user_id = CAST(:draft_creator_user_id AS uuid)
      OR EXISTS (
          SELECT 1 FROM coeus_draft_audiences audience
          WHERE audience.product_id = p.product_id
            AND audience.principal_id = CAST(:draft_principal_user_id AS uuid)
      )
  )
  AND EXISTS (
      SELECT 1
      FROM intelligence_store_product_acgs product_acg
      WHERE product_acg.product_id = p.product_id
        AND product_acg.acg_id = ANY(CAST(:acg_ids AS uuid[]))
  )
"""

VISIBLE_PRODUCTS_SQL = VISIBLE_PRODUCT_SQL.replace(
    "p.product_id = CAST(:product_id AS uuid)",
    "p.product_id = ANY(CAST(:product_ids AS uuid[]))",
)

SEARCH_PRODUCTS_BASE_SQL = """
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
  AND p.releasability = ARRAY['MOCK']::text[]
  AND p.handling_caveats = ARRAY['MOCK DATA ONLY']::text[]
  AND (
      :include_drafts
      OR p.status <> :draft_status
      OR p.created_by_user_id = CAST(:draft_creator_user_id AS uuid)
      OR EXISTS (
          SELECT 1 FROM coeus_draft_audiences audience
          WHERE audience.product_id = p.product_id
            AND audience.principal_id = CAST(:draft_principal_user_id AS uuid)
      )
  )
  AND EXISTS (
      SELECT 1
      FROM intelligence_store_product_acgs product_acg
      WHERE product_acg.product_id = p.product_id
        AND product_acg.acg_id = ANY(CAST(:acg_ids AS uuid[]))
  )
  AND (CAST(:product_type AS text) IS NULL OR p.product_type = CAST(:product_type AS text))
  AND (CAST(:source_type AS text) IS NULL OR p.source_type = CAST(:source_type AS text))
  AND (CAST(:status AS text) IS NULL OR p.status = CAST(:status AS text))
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
"""

_TITLE_ORDER_SQL = """
ORDER BY lower(p.title) ASC, p.reference ASC
LIMIT :page_size
OFFSET :offset
"""

# Newest coverage first; products with no recorded period sort last so an empty
# coverage window never outranks a dated product.
_COVERAGE_ORDER_SQL = """
ORDER BY p.time_period_start DESC NULLS LAST, lower(p.title) ASC, p.reference ASC
LIMIT :page_size
OFFSET :offset
"""

# Catalogue browse has no relevance signal to rank by, so relevance resolves to
# the deterministic title order. Every fragment is a static constant chosen by
# enum, never interpolated request text.
SEARCH_PRODUCTS_SQL_BY_SORT = {
    "relevance": SEARCH_PRODUCTS_BASE_SQL + _TITLE_ORDER_SQL,
    "title": SEARCH_PRODUCTS_BASE_SQL + _TITLE_ORDER_SQL,
    "coverage": SEARCH_PRODUCTS_BASE_SQL + _COVERAGE_ORDER_SQL,
}

SEARCH_PRODUCTS_SQL = SEARCH_PRODUCTS_SQL_BY_SORT["relevance"]

SEARCH_SUMMARY_SQL = (
    # Every fragment is a static constant; request values remain bound parameters.
    "WITH filtered_products AS ("  # noqa: S608  # nosec B608
    + SEARCH_PRODUCTS_BASE_SQL
    + """
)
SELECT
    (SELECT count(*) FROM filtered_products) AS total,
    (SELECT coalesce(jsonb_agg(entry ORDER BY entry ->> 'value'), '[]'::jsonb)
     FROM (
         SELECT jsonb_build_object('value', product_type, 'count', count(*)) AS entry
         FROM filtered_products
         GROUP BY product_type
     ) AS product_type_counts) AS product_types,
    (SELECT coalesce(jsonb_agg(entry ORDER BY entry ->> 'value'), '[]'::jsonb)
     FROM (
         SELECT jsonb_build_object('value', area_or_region, 'count', count(*)) AS entry
         FROM filtered_products
         GROUP BY area_or_region
     ) AS region_counts) AS regions,
    (SELECT coalesce(jsonb_agg(entry ORDER BY entry ->> 'value'), '[]'::jsonb)
     FROM (
         SELECT jsonb_build_object('value', tag, 'count', count(*)) AS entry
         FROM filtered_products, LATERAL unnest(tags) AS tag
         GROUP BY tag
     ) AS tag_counts) AS tags
"""
)

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
