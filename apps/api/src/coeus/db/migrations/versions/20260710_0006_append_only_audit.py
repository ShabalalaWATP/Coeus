"""add append-only audit event storage

Revision ID: 20260710_0006
Revises: 20260709_0005
Create Date: 2026-07-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260710_0006"
down_revision: str | None = "20260709_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
__all__ = ("branch_labels", "depends_on", "down_revision", "downgrade", "revision", "upgrade")


def upgrade() -> None:
    op.create_table(
        "coeus_audit_events",
        sa.Column("event_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor_user_id", sa.Text(), nullable=True),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.create_index(
        "idx_coeus_audit_events_order",
        "coeus_audit_events",
        [sa.text("occurred_at DESC"), sa.text("event_id DESC")],
    )


def downgrade() -> None:
    op.drop_index("idx_coeus_audit_events_order", table_name="coeus_audit_events")
    op.drop_table("coeus_audit_events")
