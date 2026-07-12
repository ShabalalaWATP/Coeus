"""add append-only audit event storage

Revision ID: 20260710_0006
Revises: 20260709_0005
Create Date: 2026-07-10
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260710_0006"
down_revision: str | None = "20260709_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
__all__ = ("branch_labels", "depends_on", "down_revision", "downgrade", "revision", "upgrade")

_AUDIT_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS coeus_audit_events (
    event_id uuid PRIMARY KEY,
    event_type text NOT NULL,
    occurred_at timestamptz NOT NULL,
    actor_user_id text,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb
)
"""

_AUDIT_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_coeus_audit_events_order
ON coeus_audit_events(occurred_at DESC, event_id DESC)
"""


def upgrade() -> None:
    # Older local runtimes created this exact table lazily before Alembic owned
    # the schema. Idempotent DDL lets those databases advance to head safely.
    op.execute(_AUDIT_TABLE_SQL)
    op.execute(_AUDIT_INDEX_SQL)


def downgrade() -> None:
    op.drop_index("idx_coeus_audit_events_order", table_name="coeus_audit_events")
    op.drop_table("coeus_audit_events")
