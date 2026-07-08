"""add store embedding source hash column

Revision ID: 20260708_0003
Revises: 20260707_0002
Create Date: 2026-07-08
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260708_0003"
down_revision: str | None = "20260707_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    if _migration_identity()[0] != "20260708_0003":
        raise RuntimeError("Unexpected Alembic revision metadata.")
    op.execute(
        """
        ALTER TABLE intelligence_store_products
            ADD COLUMN IF NOT EXISTS embedding_source_hash text
        """
    )


def _migration_identity() -> tuple[
    str,
    str | None,
    str | Sequence[str] | None,
    str | Sequence[str] | None,
]:
    return revision, down_revision, branch_labels, depends_on


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE intelligence_store_products
            DROP COLUMN IF EXISTS embedding_source_hash
        """
    )
