"""add ticket capacity projection

Revision ID: 20260713_0010
Revises: 20260713_0009
Create Date: 2026-07-13
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260713_0010"
down_revision: str | None = "20260713_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
__all__ = ("branch_labels", "depends_on", "down_revision", "downgrade", "revision", "upgrade")


def upgrade() -> None:
    op.execute(
        "ALTER TABLE coeus_ticket_aggregates ADD COLUMN IF NOT EXISTS requester_user_id uuid"
    )
    op.execute("ALTER TABLE coeus_ticket_aggregates ADD COLUMN IF NOT EXISTS state text")
    op.execute(
        "ALTER TABLE coeus_ticket_aggregates ADD COLUMN IF NOT EXISTS consumes_capacity boolean"
    )
    op.execute(
        """
        UPDATE coeus_ticket_aggregates SET
          requester_user_id = (payload -> 'fields' -> 'requester_user_id' ->> '__uuid__')::uuid,
          state = payload -> 'fields' -> 'state' ->> 'value',
          consumes_capacity = payload -> 'fields' -> 'state' ->> 'value'
            NOT IN ('CANCELLED', 'CLOSED_DELIVERED', 'CLOSED_EXISTING_PRODUCT_ACCEPTED')
        """
    )
    op.execute("ALTER TABLE coeus_ticket_aggregates ALTER COLUMN requester_user_id SET NOT NULL")
    op.execute("ALTER TABLE coeus_ticket_aggregates ALTER COLUMN state SET NOT NULL")
    op.execute("ALTER TABLE coeus_ticket_aggregates ALTER COLUMN consumes_capacity SET NOT NULL")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_coeus_ticket_capacity "
        "ON coeus_ticket_aggregates(requester_user_id) WHERE consumes_capacity"
    )


def downgrade() -> None:
    op.execute("DROP INDEX idx_coeus_ticket_capacity")
    op.execute("ALTER TABLE coeus_ticket_aggregates DROP COLUMN consumes_capacity")
    op.execute("ALTER TABLE coeus_ticket_aggregates DROP COLUMN state")
    op.execute("ALTER TABLE coeus_ticket_aggregates DROP COLUMN requester_user_id")
