"""add explicit legacy-calendar import evidence

Revision ID: 20260804_0035
Revises: 20260804_0034
Create Date: 2026-08-04
"""

from collections.abc import Sequence

from alembic import op

from coeus.persistence.calendar_import_schema import calendar_import_schema_statements

revision: str = "20260804_0035"
down_revision: str | None = "20260804_0034"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
__all__ = ("branch_labels", "depends_on", "down_revision", "downgrade", "revision", "upgrade")


def upgrade() -> None:
    for statement in calendar_import_schema_statements():
        op.execute(statement)


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_calendar_import_records_immutable "
        "ON calendar_legacy_import_records"
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_calendar_import_commands_immutable ON calendar_import_commands"
    )
    op.execute("DROP FUNCTION IF EXISTS reject_calendar_import_evidence_mutation()")
    op.execute("DROP TABLE IF EXISTS calendar_legacy_import_records")
    op.execute("DROP TABLE IF EXISTS calendar_import_commands")
