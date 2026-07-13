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

SEARCH_PRODUCTS_SQL = (
    SEARCH_PRODUCTS_BASE_SQL
    + """
ORDER BY lower(p.title) ASC, p.reference ASC
LIMIT :page_size
OFFSET :offset
"""
)

SEARCH_SUMMARY_SQL = (
    # Every fragment is a static constant; request values remain bound parameters.
    "WITH filtered_products AS ("  # noqa: S608  # nosec B608
    + SEARCH_PRODUCTS_BASE_SQL
    + """
)
SELECT
    (SELECT count(*) FROM filtered_products) AS total,
    (SELECT coalesce(array_agg(DISTINCT product_type ORDER BY product_type), ARRAY[]::text[])
     FROM filtered_products) AS product_types,
    (SELECT coalesce(array_agg(DISTINCT area_or_region ORDER BY area_or_region),
        ARRAY[]::text[])
     FROM filtered_products) AS regions,
    (SELECT coalesce(array_agg(DISTINCT tag ORDER BY tag), ARRAY[]::text[])
     FROM filtered_products, LATERAL unnest(tags) AS tag) AS tags
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

HYBRID_PRODUCTS_SQL = """
WITH scoped AS (
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
        p.updated_at,
        p.search_document,
        p.embedding
    FROM intelligence_store_products p
    WHERE p.status <> :archived_status
      AND p.classification_level <= :clearance_level
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
              AND (CAST(:date_from AS date) IS NULL
                  OR coalesce(p.time_period_end, p.time_period_start) >= CAST(:date_from AS date))
              AND (CAST(:date_to AS date) IS NULL
                  OR p.time_period_start <= CAST(:date_to AS date))
          )
      )
),
lexical AS (
    SELECT
        product_id,
        ts_rank_cd(search_document, websearch_to_tsquery('english', CAST(:query AS text)))
            AS lexical_score,
        row_number() OVER (
            ORDER BY ts_rank_cd(search_document, websearch_to_tsquery('english',
                CAST(:query AS text))) DESC, title ASC
        ) AS lexical_rank
    FROM scoped
    WHERE CAST(:query AS text) IS NOT NULL
      AND search_document @@ websearch_to_tsquery('english', CAST(:query AS text))
    ORDER BY ts_rank_cd(search_document, websearch_to_tsquery('english',
        CAST(:query AS text))) DESC, title ASC
    LIMIT :leg_limit
),
semantic AS (
    SELECT
        product_id,
        1 - (embedding <=> CAST(:query_embedding AS vector)) AS vector_score,
        row_number() OVER (
            ORDER BY embedding <=> CAST(:query_embedding AS vector), title ASC
        ) AS vector_rank
    FROM scoped
    WHERE CAST(:query_embedding AS text) IS NOT NULL
      AND embedding IS NOT NULL
      AND (1 - (embedding <=> CAST(:query_embedding AS vector))) >= :vector_similarity_floor
    ORDER BY embedding <=> CAST(:query_embedding AS vector), title ASC
    LIMIT :leg_limit
),
selected AS (
    SELECT product_id FROM lexical
    UNION
    SELECT product_id FROM semantic
)
SELECT
    scoped.*,
    lexical.lexical_rank,
    lexical.lexical_score,
    semantic.vector_rank,
    semantic.vector_score
FROM scoped
JOIN selected ON selected.product_id = scoped.product_id
LEFT JOIN lexical ON lexical.product_id = scoped.product_id
LEFT JOIN semantic ON semantic.product_id = scoped.product_id
ORDER BY
    coalesce(lexical.lexical_rank, 9999),
    coalesce(semantic.vector_rank, 9999),
    scoped.title ASC
"""
