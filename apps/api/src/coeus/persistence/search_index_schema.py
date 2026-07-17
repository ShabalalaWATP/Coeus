from collections.abc import Sequence


def search_index_schema_statements() -> Sequence[str]:
    return (
        """
        CREATE TABLE IF NOT EXISTS search_index_profiles (
          profile_id uuid PRIMARY KEY,
          provider text NOT NULL,
          model text NOT NULL,
          dimensions integer NOT NULL CHECK (dimensions = 1536),
          generation integer NOT NULL CHECK (generation > 0),
          space_id text NOT NULL UNIQUE,
          status text NOT NULL CHECK (status IN ('indexing', 'ready', 'failed')),
          is_active boolean NOT NULL DEFAULT false,
          corpus_version text NOT NULL,
          product_count integer NOT NULL DEFAULT 0,
          chunk_count integer NOT NULL DEFAULT 0,
          indexed_count integer NOT NULL DEFAULT 0,
          failed_count integer NOT NULL DEFAULT 0,
          created_by_user_id uuid NOT NULL,
          created_at timestamptz NOT NULL DEFAULT now(),
          completed_at timestamptz,
          error_code text
        )
        """,
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_search_index_one_active
        ON search_index_profiles(is_active) WHERE is_active
        """,
        """
        CREATE TABLE IF NOT EXISTS intelligence_store_search_chunks (
          chunk_id uuid PRIMARY KEY,
          product_id uuid NOT NULL REFERENCES intelligence_store_products(product_id)
            ON DELETE CASCADE,
          asset_id uuid,
          asset_name text NOT NULL,
          asset_sha256 char(64),
          page_number integer NOT NULL CHECK (page_number >= 0),
          chunk_index integer NOT NULL CHECK (chunk_index >= 0),
          content text NOT NULL CHECK (char_length(content) BETWEEN 1 AND 12000),
          content_hash char(64) NOT NULL,
          extractor_version text NOT NULL,
          chunker_version text NOT NULL,
          search_document tsvector NOT NULL,
          UNIQUE(product_id, asset_id, page_number, chunk_index, content_hash)
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_store_chunks_product
        ON intelligence_store_search_chunks(product_id)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_store_chunks_search_document
        ON intelligence_store_search_chunks USING gin(search_document)
        """,
        """
        CREATE TABLE IF NOT EXISTS intelligence_store_chunk_embeddings (
          profile_id uuid NOT NULL REFERENCES search_index_profiles(profile_id)
            ON DELETE CASCADE,
          chunk_id uuid NOT NULL REFERENCES intelligence_store_search_chunks(chunk_id)
            ON DELETE CASCADE,
          source_hash char(64) NOT NULL,
          embedding vector(1536) NOT NULL,
          indexed_at timestamptz NOT NULL DEFAULT now(),
          PRIMARY KEY(profile_id, chunk_id)
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_store_chunk_embeddings_vector
        ON intelligence_store_chunk_embeddings USING hnsw (embedding vector_cosine_ops)
        """,
        """
        CREATE TABLE IF NOT EXISTS ticket_search_documents (
          ticket_id uuid PRIMARY KEY,
          state text NOT NULL,
          content text NOT NULL CHECK (char_length(content) BETWEEN 1 AND 32000),
          content_hash char(64) NOT NULL,
          search_document tsvector NOT NULL,
          updated_at timestamptz NOT NULL DEFAULT now()
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_ticket_search_document
        ON ticket_search_documents USING gin(search_document)
        """,
        """
        CREATE TABLE IF NOT EXISTS ticket_search_embeddings (
          profile_id uuid NOT NULL REFERENCES search_index_profiles(profile_id)
            ON DELETE CASCADE,
          ticket_id uuid NOT NULL REFERENCES ticket_search_documents(ticket_id)
            ON DELETE CASCADE,
          source_hash char(64) NOT NULL,
          embedding vector(1536) NOT NULL,
          indexed_at timestamptz NOT NULL DEFAULT now(),
          PRIMARY KEY(profile_id, ticket_id)
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_ticket_search_embeddings_vector
        ON ticket_search_embeddings USING hnsw (embedding vector_cosine_ops)
        """,
        """
        CREATE TABLE IF NOT EXISTS intelligence_store_asset_index_state (
          profile_id uuid NOT NULL REFERENCES search_index_profiles(profile_id)
            ON DELETE CASCADE,
          product_id uuid NOT NULL REFERENCES intelligence_store_products(product_id)
            ON DELETE CASCADE,
          asset_id uuid NOT NULL,
          asset_sha256 char(64) NOT NULL,
          status text NOT NULL CHECK (status IN ('indexed', 'unsupported', 'failed')),
          page_count integer NOT NULL DEFAULT 0,
          chunk_count integer NOT NULL DEFAULT 0,
          error_code text,
          PRIMARY KEY(profile_id, asset_id)
        )
        """,
    )
