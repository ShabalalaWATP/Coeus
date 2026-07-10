"""switch store embedding index to hnsw

Revision ID: 20260707_0002
Revises: 20260706_0001
Create Date: 2026-07-07
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260707_0002"
down_revision: str | None = "20260706_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
__all__ = ("branch_labels", "depends_on", "down_revision", "downgrade", "revision", "upgrade")


def upgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_store_products_embedding")
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_store_products_embedding
            ON intelligence_store_products USING hnsw (embedding vector_cosine_ops)
            WHERE embedding IS NOT NULL
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_store_products_embedding")
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_store_products_embedding
            ON intelligence_store_products USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = 64)
            WHERE embedding IS NOT NULL
        """
    )
