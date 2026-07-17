"""add durable outbox delivery state

Revision ID: 20260713_0011
Revises: 20260713_0010
Create Date: 2026-07-13
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260713_0011"
down_revision: str | None = "20260713_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
__all__ = ("branch_labels", "depends_on", "down_revision", "downgrade", "revision", "upgrade")


def upgrade() -> None:
    op.execute(
        "ALTER TABLE coeus_outbox ADD COLUMN IF NOT EXISTS "
        "available_at timestamptz NOT NULL DEFAULT now()"
    )
    op.execute(
        "ALTER TABLE coeus_outbox ADD COLUMN IF NOT EXISTS attempt_count integer NOT NULL DEFAULT 0"
    )
    op.execute("ALTER TABLE coeus_outbox ADD COLUMN IF NOT EXISTS claimed_by uuid")
    op.execute("ALTER TABLE coeus_outbox ADD COLUMN IF NOT EXISTS claim_expires_at timestamptz")
    op.execute("ALTER TABLE coeus_outbox ADD COLUMN IF NOT EXISTS last_error text")
    op.execute("ALTER TABLE coeus_outbox ADD COLUMN IF NOT EXISTS dead_lettered_at timestamptz")
    op.execute(
        """
        DO $constraint$
        BEGIN
          IF NOT EXISTS (
            SELECT 1 FROM pg_constraint
            WHERE conrelid = 'coeus_outbox'::regclass
              AND conname IN (
                'ck_coeus_outbox_attempt_count',
                'coeus_outbox_attempt_count_check'
              )
          ) THEN
            ALTER TABLE coeus_outbox
              ADD CONSTRAINT ck_coeus_outbox_attempt_count CHECK (attempt_count >= 0);
          END IF;
        END
        $constraint$
        """
    )
    op.execute("DROP INDEX IF EXISTS idx_coeus_outbox_pending")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_coeus_outbox_pending "
        "ON coeus_outbox(available_at, created_at, event_id) "
        "WHERE delivered_at IS NULL AND dead_lettered_at IS NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX idx_coeus_outbox_pending")
    op.execute(
        "CREATE INDEX idx_coeus_outbox_pending ON coeus_outbox(created_at, event_id) "
        "WHERE delivered_at IS NULL"
    )
    op.execute("ALTER TABLE coeus_outbox DROP CONSTRAINT ck_coeus_outbox_attempt_count")
    op.execute("ALTER TABLE coeus_outbox DROP COLUMN dead_lettered_at")
    op.execute("ALTER TABLE coeus_outbox DROP COLUMN last_error")
    op.execute("ALTER TABLE coeus_outbox DROP COLUMN claim_expires_at")
    op.execute("ALTER TABLE coeus_outbox DROP COLUMN claimed_by")
    op.execute("ALTER TABLE coeus_outbox DROP COLUMN attempt_count")
    op.execute("ALTER TABLE coeus_outbox DROP COLUMN available_at")
