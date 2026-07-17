"""add generation-aware grounded search index

Revision ID: 20260717_0013
Revises: 20260713_0012
Create Date: 2026-07-17
"""

from collections.abc import Sequence

from alembic import op

from coeus.persistence.search_index_schema import search_index_schema_statements

revision: str = "20260717_0013"
down_revision: str | None = "20260713_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
__all__ = ("branch_labels", "depends_on", "down_revision", "downgrade", "revision", "upgrade")


def upgrade() -> None:
    for statement in search_index_schema_statements():
        op.execute(statement)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS intelligence_store_asset_index_state")
    op.execute("DROP TABLE IF EXISTS ticket_search_embeddings")
    op.execute("DROP TABLE IF EXISTS ticket_search_documents")
    op.execute("DROP TABLE IF EXISTS intelligence_store_chunk_embeddings")
    op.execute("DROP TABLE IF EXISTS intelligence_store_search_chunks")
    op.execute("DROP TABLE IF EXISTS search_index_profiles")
