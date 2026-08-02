"""scope ticket search documents to a generation

Revision ID: 20260801_0016
Revises: 20260727_0015
Create Date: 2026-08-01
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260801_0016"
down_revision: str | None = "20260727_0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
__all__ = ("branch_labels", "depends_on", "down_revision", "downgrade", "revision", "upgrade")


def upgrade() -> None:
    op.execute(
        "UPDATE search_index_profiles SET status = 'failed', is_active = false, "
        "error_code = 'worker_interrupted', completed_at = now() WHERE status = 'indexing'"
    )
    op.execute(
        "UPDATE search_index_profiles SET status = 'failed', is_active = false, "
        "error_code = 'index_write_failed', completed_at = now() WHERE status = 'ready'"
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_search_index_one_building "
        "ON search_index_profiles(status) WHERE status = 'indexing'"
    )
    op.execute("DROP TABLE ticket_search_embeddings")
    op.execute("DROP TABLE ticket_search_documents")
    _create_generation_ticket_tables()


def downgrade() -> None:
    op.execute("DROP TABLE ticket_search_embeddings")
    op.execute("DROP TABLE ticket_search_documents")
    op.execute("DROP INDEX IF EXISTS idx_search_index_one_building")
    op.execute(
        """
        CREATE TABLE ticket_search_documents (
          ticket_id uuid PRIMARY KEY,
          state text NOT NULL,
          content text NOT NULL CHECK (char_length(content) BETWEEN 1 AND 32000),
          content_hash char(64) NOT NULL,
          search_document tsvector NOT NULL,
          updated_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE INDEX idx_ticket_search_document "
        "ON ticket_search_documents USING gin(search_document)"
    )
    op.execute(
        """
        CREATE TABLE ticket_search_embeddings (
          profile_id uuid NOT NULL REFERENCES search_index_profiles(profile_id)
            ON DELETE CASCADE,
          ticket_id uuid NOT NULL REFERENCES ticket_search_documents(ticket_id)
            ON DELETE CASCADE,
          source_hash char(64) NOT NULL,
          embedding vector(1536) NOT NULL,
          indexed_at timestamptz NOT NULL DEFAULT now(),
          PRIMARY KEY(profile_id, ticket_id)
        )
        """
    )
    op.execute(
        "CREATE INDEX idx_ticket_search_embeddings_vector "
        "ON ticket_search_embeddings USING hnsw (embedding vector_cosine_ops)"
    )


def _create_generation_ticket_tables() -> None:
    op.execute(
        """
        CREATE TABLE ticket_search_documents (
          profile_id uuid NOT NULL REFERENCES search_index_profiles(profile_id)
            ON DELETE CASCADE,
          ticket_id uuid NOT NULL,
          state text NOT NULL,
          content text NOT NULL CHECK (char_length(content) BETWEEN 1 AND 32000),
          content_hash char(64) NOT NULL,
          search_document tsvector NOT NULL,
          updated_at timestamptz NOT NULL DEFAULT now(),
          PRIMARY KEY(profile_id, ticket_id)
        )
        """
    )
    op.execute(
        "CREATE INDEX idx_ticket_search_document "
        "ON ticket_search_documents USING gin(search_document)"
    )
    op.execute(
        """
        CREATE TABLE ticket_search_embeddings (
          profile_id uuid NOT NULL REFERENCES search_index_profiles(profile_id)
            ON DELETE CASCADE,
          ticket_id uuid NOT NULL,
          source_hash char(64) NOT NULL,
          embedding vector(1536) NOT NULL,
          indexed_at timestamptz NOT NULL DEFAULT now(),
          PRIMARY KEY(profile_id, ticket_id),
          FOREIGN KEY(profile_id, ticket_id)
            REFERENCES ticket_search_documents(profile_id, ticket_id) ON DELETE CASCADE
        )
        """
    )
    op.execute(
        "CREATE INDEX idx_ticket_search_embeddings_vector "
        "ON ticket_search_embeddings USING hnsw (embedding vector_cosine_ops)"
    )
