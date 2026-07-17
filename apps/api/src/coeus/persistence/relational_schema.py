from collections.abc import Sequence

from sqlalchemy import text
from sqlalchemy.engine import Connection

from coeus.persistence.search_index_schema import search_index_schema_statements


def store_schema_statements() -> Sequence[str]:
    return (
        "CREATE EXTENSION IF NOT EXISTS vector",
        """
        CREATE TABLE IF NOT EXISTS intelligence_store_products (
            product_id uuid PRIMARY KEY,
            reference text NOT NULL UNIQUE,
            title text NOT NULL,
            summary text NOT NULL,
            description text NOT NULL,
            product_type text NOT NULL,
            source_type text NOT NULL,
            owner_team text NOT NULL,
            area_or_region text NOT NULL,
            classification_level integer NOT NULL CHECK (classification_level BETWEEN 0 AND 5),
            releasability text[] NOT NULL DEFAULT '{}',
            handling_caveats text[] NOT NULL DEFAULT '{}',
            tags text[] NOT NULL DEFAULT '{}',
            semantic_labels text[] NOT NULL DEFAULT '{}',
            acg_ids uuid[] NOT NULL DEFAULT '{}',
            status text NOT NULL,
            time_period_start date,
            time_period_end date,
            geojson_ref text,
            bounding_box jsonb,
            created_by_user_id uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            search_document tsvector NOT NULL DEFAULT ''::tsvector,
            embedding vector(384),
            embedding_source_hash text
        )
        """,
        """
        ALTER TABLE intelligence_store_products
            ADD COLUMN IF NOT EXISTS embedding_source_hash text
        """,
        """
        CREATE TABLE IF NOT EXISTS intelligence_store_assets (
            asset_id uuid PRIMARY KEY,
            product_id uuid NOT NULL REFERENCES intelligence_store_products(product_id)
                ON DELETE CASCADE,
            name text NOT NULL,
            asset_type text NOT NULL,
            mime_type text NOT NULL,
            size_bytes bigint NOT NULL CHECK (size_bytes > 0),
            sha256 char(64) NOT NULL,
            object_key text NOT NULL UNIQUE,
            preview_kind text NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now()
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS intelligence_store_product_acgs (
            product_id uuid NOT NULL REFERENCES intelligence_store_products(product_id)
                ON DELETE CASCADE,
            acg_id uuid NOT NULL,
            PRIMARY KEY (product_id, acg_id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS intelligence_store_semantic_labels (
            product_id uuid NOT NULL REFERENCES intelligence_store_products(product_id)
                ON DELETE CASCADE,
            label text NOT NULL,
            PRIMARY KEY (product_id, label)
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_store_products_status
            ON intelligence_store_products(status)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_store_products_owner_team
            ON intelligence_store_products(owner_team)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_store_products_product_type
            ON intelligence_store_products(product_type)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_store_products_area_or_region
            ON intelligence_store_products(area_or_region)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_store_products_tags
            ON intelligence_store_products USING gin(tags)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_store_products_semantic_labels
            ON intelligence_store_products USING gin(semantic_labels)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_store_products_search_document
            ON intelligence_store_products USING gin(search_document)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_store_products_embedding
            ON intelligence_store_products USING hnsw (embedding vector_cosine_ops)
            WHERE embedding IS NOT NULL
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_store_product_acgs_acg
            ON intelligence_store_product_acgs(acg_id)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_store_semantic_labels_label
            ON intelligence_store_semantic_labels(label)
        """,
    )


def ensure_relational_schema(connection: Connection) -> None:
    for statement in (*store_schema_statements(), *search_index_schema_statements()):
        connection.execute(text(statement))
