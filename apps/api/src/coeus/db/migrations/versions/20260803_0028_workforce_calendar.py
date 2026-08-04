"""add canonical workforce calendars

Revision ID: 20260803_0028
Revises: 20260803_0027
Create Date: 2026-08-03
"""

from collections.abc import Sequence

from alembic import op

from coeus.persistence.workforce_calendar_schema import workforce_calendar_schema_statements

revision: str = "20260803_0028"
down_revision: str | None = "20260803_0027"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
__all__ = ("branch_labels", "depends_on", "down_revision", "downgrade", "revision", "upgrade")


def upgrade() -> None:
    for statement in workforce_calendar_schema_statements():
        op.execute(statement)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_calendar_history_immutable ON calendar_event_versions")
    op.execute("DROP FUNCTION IF EXISTS reject_calendar_history_mutation()")
    op.execute("DROP TRIGGER IF EXISTS trg_calendar_event_no_delete ON calendar_events")
    op.execute("DROP FUNCTION IF EXISTS reject_calendar_event_delete()")
    for table_name in (
        "calendar_event_commands",
        "calendar_event_versions",
        "calendar_event_exceptions",
        "calendar_event_scopes",
        "calendar_events",
    ):
        op.execute(f"DROP TABLE IF EXISTS {table_name}")
