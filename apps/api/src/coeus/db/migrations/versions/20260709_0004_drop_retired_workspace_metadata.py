"""drop retired store workspace metadata column

Revision ID: 20260709_0004
Revises: 20260708_0003
Create Date: 2026-07-09
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260709_0004"
down_revision: str | None = "20260708_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
__all__ = ("branch_labels", "depends_on", "down_revision", "downgrade", "revision", "upgrade")


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE intelligence_store_products
            DROP COLUMN IF EXISTS project_id
        """
    )


def downgrade() -> None:
    """Keep the retired workspace column removed on downgrade."""
