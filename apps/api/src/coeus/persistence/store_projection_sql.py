SELECT_PRODUCTS_SQL = """
SELECT
    product_id,
    reference,
    title,
    summary,
    description,
    product_type,
    source_type,
    owner_team,
    area_or_region,
    classification_level,
    releasability,
    handling_caveats,
    tags,
    semantic_labels,
    acg_ids,
    project_id,
    status,
    time_period_start,
    time_period_end,
    geojson_ref,
    bounding_box,
    created_by_user_id,
    created_at,
    updated_at
FROM intelligence_store_products
ORDER BY title ASC
"""

SELECT_ASSETS_SQL = """
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
ORDER BY name ASC
"""

SELECT_ACGS_SQL = """
SELECT product_id, acg_id
FROM intelligence_store_product_acgs
ORDER BY acg_id ASC
"""

SELECT_LABELS_SQL = """
SELECT product_id, label
FROM intelligence_store_semantic_labels
ORDER BY label ASC
"""

UPSERT_PRODUCT_SQL = """
INSERT INTO intelligence_store_products (
    product_id,
    reference,
    title,
    summary,
    description,
    product_type,
    source_type,
    owner_team,
    area_or_region,
    classification_level,
    releasability,
    handling_caveats,
    tags,
    semantic_labels,
    acg_ids,
    project_id,
    status,
    time_period_start,
    time_period_end,
    geojson_ref,
    bounding_box,
    created_by_user_id,
    created_at,
    updated_at,
    search_document,
    embedding,
    embedding_source_hash
) VALUES (
    CAST(:product_id AS uuid),
    :reference,
    :title,
    :summary,
    :description,
    :product_type,
    :source_type,
    :owner_team,
    :area_or_region,
    :classification_level,
    CAST(:releasability AS text[]),
    CAST(:handling_caveats AS text[]),
    CAST(:tags AS text[]),
    CAST(:semantic_labels AS text[]),
    CAST(:acg_ids AS uuid[]),
    CAST(:project_id AS uuid),
    :status,
    CAST(:time_period_start AS date),
    CAST(:time_period_end AS date),
    :geojson_ref,
    CAST(:bounding_box AS jsonb),
    CAST(:created_by_user_id AS uuid),
    :created_at,
    :updated_at,
    to_tsvector(
        'english',
        concat_ws(
            ' ',
            CAST(:title AS text),
            CAST(:summary AS text),
            CAST(:description AS text),
            CAST(:product_type AS text),
            CAST(:source_type AS text),
            CAST(:owner_team AS text),
            CAST(:area_or_region AS text),
            array_to_string(CAST(:tags AS text[]), ' '),
            array_to_string(CAST(:semantic_labels AS text[]), ' ')
        )
    ),
    CAST(:embedding AS vector),
    :embedding_source_hash
)
ON CONFLICT (product_id)
DO UPDATE SET
    reference = EXCLUDED.reference,
    title = EXCLUDED.title,
    summary = EXCLUDED.summary,
    description = EXCLUDED.description,
    product_type = EXCLUDED.product_type,
    source_type = EXCLUDED.source_type,
    owner_team = EXCLUDED.owner_team,
    area_or_region = EXCLUDED.area_or_region,
    classification_level = EXCLUDED.classification_level,
    releasability = EXCLUDED.releasability,
    handling_caveats = EXCLUDED.handling_caveats,
    tags = EXCLUDED.tags,
    semantic_labels = EXCLUDED.semantic_labels,
    acg_ids = EXCLUDED.acg_ids,
    project_id = EXCLUDED.project_id,
    status = EXCLUDED.status,
    time_period_start = EXCLUDED.time_period_start,
    time_period_end = EXCLUDED.time_period_end,
    geojson_ref = EXCLUDED.geojson_ref,
    bounding_box = EXCLUDED.bounding_box,
    created_by_user_id = EXCLUDED.created_by_user_id,
    created_at = EXCLUDED.created_at,
    updated_at = EXCLUDED.updated_at,
    search_document = EXCLUDED.search_document,
    embedding = COALESCE(CAST(:embedding AS vector), intelligence_store_products.embedding),
    embedding_source_hash = COALESCE(
        :embedding_source_hash, intelligence_store_products.embedding_source_hash
    )
"""

SELECT_EMBEDDING_HASHES_SQL = """
SELECT product_id, embedding_source_hash
FROM intelligence_store_products
WHERE embedding IS NOT NULL
  AND product_id = ANY(CAST(:product_ids AS uuid[]))
"""

SELECT_MISSING_EMBEDDING_IDS_SQL = """
SELECT product_id
FROM intelligence_store_products
WHERE embedding IS NULL
ORDER BY product_id ASC
LIMIT :batch_size
"""

UPDATE_PRODUCT_EMBEDDING_SQL = """
UPDATE intelligence_store_products
SET embedding = CAST(:embedding AS vector),
    embedding_source_hash = :embedding_source_hash
WHERE product_id = CAST(:product_id AS uuid)
  AND embedding IS NULL
"""

INSERT_ASSET_SQL = """
INSERT INTO intelligence_store_assets (
    asset_id, product_id, name, asset_type, mime_type, size_bytes, sha256, object_key, preview_kind
) VALUES (
    CAST(:asset_id AS uuid), CAST(:product_id AS uuid), :name, :asset_type, :mime_type,
    :size_bytes, :sha256, :object_key, :preview_kind
)
"""

INSERT_ACG_SQL = """
INSERT INTO intelligence_store_product_acgs (product_id, acg_id)
VALUES (CAST(:product_id AS uuid), CAST(:acg_id AS uuid))
ON CONFLICT DO NOTHING
"""

INSERT_LABEL_SQL = """
INSERT INTO intelligence_store_semantic_labels (product_id, label)
VALUES (CAST(:product_id AS uuid), :label)
ON CONFLICT DO NOTHING
"""

DELETE_ASSETS_SQL = """
DELETE FROM intelligence_store_assets
WHERE product_id = CAST(:product_id AS uuid)
"""

DELETE_ACGS_SQL = """
DELETE FROM intelligence_store_product_acgs
WHERE product_id = CAST(:product_id AS uuid)
"""

DELETE_LABELS_SQL = """
DELETE FROM intelligence_store_semantic_labels
WHERE product_id = CAST(:product_id AS uuid)
"""
