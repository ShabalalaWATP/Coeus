"""support bounded calendar occurrence actions

Revision ID: 20260804_0038
Revises: 20260804_0037
Create Date: 2026-08-04
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260804_0038"
down_revision: str | None = "20260804_0037"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
__all__ = ("branch_labels", "depends_on", "down_revision", "downgrade", "revision", "upgrade")

_CHECK = "calendar_event_commands_command_type_check"
_TYPES = "'create','update','cancel','update_occurrence','cancel_occurrence','update_future'"


def upgrade() -> None:
    op.execute(f"ALTER TABLE calendar_event_commands DROP CONSTRAINT IF EXISTS {_CHECK}")
    op.execute("ALTER TABLE calendar_event_commands ALTER COLUMN command_type TYPE varchar(24)")
    op.execute(
        "ALTER TABLE calendar_event_commands ADD COLUMN IF NOT EXISTS future_event_id uuid NULL"
    )
    op.execute(
        "DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE "
        "conname='calendar_event_commands_future_event_fk') THEN "
        "ALTER TABLE calendar_event_commands ADD CONSTRAINT "
        "calendar_event_commands_future_event_fk FOREIGN KEY(future_event_id) "
        "REFERENCES calendar_events(event_id); END IF; END $$"
    )
    op.execute(
        f"ALTER TABLE calendar_event_commands ADD CONSTRAINT {_CHECK} "
        f"CHECK(command_type IN ({_TYPES}))"
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$ BEGIN
          IF EXISTS (
            SELECT 1 FROM calendar_event_commands
            WHERE command_type IN ('update_occurrence','cancel_occurrence','update_future')
               OR future_event_id IS NOT NULL
          ) THEN
            RAISE EXCEPTION
              'downgrade refused: calendar occurrence commands require revision 0038';
          END IF;
        END $$
        """
    )
    op.execute(f"ALTER TABLE calendar_event_commands DROP CONSTRAINT IF EXISTS {_CHECK}")
    op.execute(
        f"ALTER TABLE calendar_event_commands ADD CONSTRAINT {_CHECK} "
        "CHECK(command_type IN ('create','update','cancel'))"
    )
    op.execute(
        "ALTER TABLE calendar_event_commands DROP CONSTRAINT "
        "calendar_event_commands_future_event_fk"
    )
    op.execute("ALTER TABLE calendar_event_commands DROP COLUMN future_event_id")
    op.execute("ALTER TABLE calendar_event_commands ALTER COLUMN command_type TYPE varchar(16)")
