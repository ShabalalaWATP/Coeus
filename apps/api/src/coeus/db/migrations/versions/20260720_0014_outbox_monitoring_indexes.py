"""add outbox monitoring indexes

Revision ID: 20260720_0014
Revises: 20260717_0013
Create Date: 2026-07-20
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260720_0014"
down_revision: str | None = "20260717_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
__all__ = ("branch_labels", "depends_on", "down_revision", "downgrade", "revision", "upgrade")


def upgrade() -> None:
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_coeus_outbox_dead_letters "
        "ON coeus_outbox(dead_lettered_at, event_id) "
        "WHERE delivered_at IS NULL AND dead_lettered_at IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_coeus_outbox_dead_letters")
