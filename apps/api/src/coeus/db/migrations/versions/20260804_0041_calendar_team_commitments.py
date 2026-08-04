"""add canonical team commitments and deduplication identity

Revision ID: 20260804_0041
Revises: 20260804_0040
Create Date: 2026-08-04
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260804_0041"
down_revision: str | None = "20260804_0040"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
__all__ = ("branch_labels", "depends_on", "down_revision", "downgrade", "revision", "upgrade")


def upgrade() -> None:
    op.execute("ALTER TABLE calendar_events ADD COLUMN deduplication_key varchar(128)")
    op.execute(
        "CREATE INDEX ix_calendar_events_deduplication_key "
        "ON calendar_events(owner_user_id,deduplication_key) "
        "WHERE deduplication_key IS NOT NULL"
    )
    op.execute(
        """
        CREATE TABLE calendar_commitment_responses (
          event_id uuid PRIMARY KEY REFERENCES calendar_events(event_id),
          subject_user_id uuid NOT NULL,
          response_state varchar(16) NOT NULL DEFAULT 'pending'
            CHECK(response_state IN ('pending','acknowledged','disputed')),
          response_version integer NOT NULL DEFAULT 1 CHECK(response_version >= 1),
          responded_at timestamptz,
          response_reason_hash char(64),
          updated_at timestamptz NOT NULL DEFAULT transaction_timestamp(),
          CHECK((response_state='pending')=(responded_at IS NULL)),
          CHECK((response_state='disputed')=(response_reason_hash IS NOT NULL))
        )
        """
    )
    op.execute(
        """
        CREATE TABLE calendar_commitment_notifications (
          notification_id uuid PRIMARY KEY,
          event_id uuid NOT NULL REFERENCES calendar_events(event_id),
          recipient_user_id uuid NOT NULL,
          notification_type varchar(24) NOT NULL CHECK(
            notification_type IN ('created','changed','cancelled','acknowledged','disputed')
          ),
          created_at timestamptz NOT NULL DEFAULT transaction_timestamp(),
          read_at timestamptz,
          UNIQUE(event_id,recipient_user_id,notification_type,created_at)
        )
        """
    )
    op.execute(
        "CREATE INDEX ix_calendar_commitment_notifications_recipient "
        "ON calendar_commitment_notifications(recipient_user_id,created_at DESC)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE calendar_commitment_notifications")
    op.execute("DROP TABLE calendar_commitment_responses")
    op.execute("DROP INDEX ix_calendar_events_deduplication_key")
    op.execute("ALTER TABLE calendar_events DROP COLUMN deduplication_key")
