"""add versioned ticket shadow rows and outbox

Revision ID: 20260713_0008
Revises: 20260713_0007
Create Date: 2026-07-13
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260713_0008"
down_revision: str | None = "20260713_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
__all__ = ("branch_labels", "depends_on", "down_revision", "downgrade", "revision", "upgrade")


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS coeus_ticket_aggregates (
            ticket_id uuid PRIMARY KEY,
            version bigint NOT NULL CHECK (version > 0),
            payload jsonb NOT NULL,
            canonical_hash text NOT NULL,
            updated_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS coeus_outbox (
            event_id uuid PRIMARY KEY,
            aggregate_id uuid NOT NULL,
            aggregate_version bigint NOT NULL,
            event_type text NOT NULL,
            payload jsonb NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            delivered_at timestamptz,
            UNIQUE (aggregate_id, aggregate_version, event_type)
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_coeus_outbox_pending "
        "ON coeus_outbox(created_at, event_id) "
        "WHERE delivered_at IS NULL"
    )
    op.execute(
        """
        DO $backfill$
        BEGIN
          IF EXISTS (
            SELECT 1 FROM pg_attribute
            WHERE attrelid = 'coeus_ticket_aggregates'::regclass
              AND attname = 'requester_user_id'
              AND NOT attisdropped
          ) THEN
            INSERT INTO coeus_ticket_aggregates(
              ticket_id,
              requester_user_id,
              state,
              consumes_capacity,
              version,
              payload,
              canonical_hash
            )
            SELECT
              ((item -> 'fields' -> 'ticket_id' ->> '__uuid__')::uuid),
              ((item -> 'fields' -> 'requester_user_id' ->> '__uuid__')::uuid),
              item -> 'fields' -> 'state' ->> 'value',
              item -> 'fields' -> 'state' ->> 'value'
                NOT IN ('CANCELLED', 'CLOSED_DELIVERED', 'CLOSED_EXISTING_PRODUCT_ACCEPTED'),
              1,
              item,
              md5(item::text)
            FROM coeus_state,
                 LATERAL jsonb_array_elements(payload -> 'tickets') AS item
            WHERE namespace = 'tickets'
              AND jsonb_typeof(payload -> 'tickets') = 'array'
            ON CONFLICT (ticket_id) DO NOTHING;
          ELSE
            INSERT INTO coeus_ticket_aggregates(ticket_id, version, payload, canonical_hash)
            SELECT
              ((item -> 'fields' -> 'ticket_id' ->> '__uuid__')::uuid),
              1,
              item,
              md5(item::text)
            FROM coeus_state,
                 LATERAL jsonb_array_elements(payload -> 'tickets') AS item
            WHERE namespace = 'tickets'
              AND jsonb_typeof(payload -> 'tickets') = 'array'
            ON CONFLICT (ticket_id) DO NOTHING;
          END IF;
        END
        $backfill$
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE coeus_outbox")
    op.execute("DROP TABLE coeus_ticket_aggregates")
