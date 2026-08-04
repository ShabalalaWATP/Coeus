"""add workspace saved views, templates and work updates

Revision ID: 20260804_0040
Revises: 20260804_0039
Create Date: 2026-08-04
"""

from collections.abc import Sequence

from alembic import op

from coeus.persistence.workspace_productivity_schema import (
    workspace_productivity_schema_statements,
)

revision: str = "20260804_0040"
down_revision: str | None = "20260804_0039"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
__all__ = ("branch_labels", "depends_on", "down_revision", "downgrade", "revision", "upgrade")


def upgrade() -> None:
    for statement in workspace_productivity_schema_statements():
        op.execute(statement)


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_workspace_productivity_commands_immutable "
        "ON workspace_productivity_commands"
    )
    op.execute("DROP FUNCTION IF EXISTS reject_workspace_productivity_command_mutation()")
    op.execute("DROP TABLE IF EXISTS workspace_productivity_commands")
    op.execute("DROP TABLE IF EXISTS workspace_delivery_preferences")
    op.execute("DROP TABLE IF EXISTS workspace_store_links")
    op.execute("DROP TABLE IF EXISTS workspace_work_updates")
    op.execute("DROP TABLE IF EXISTS team_work_templates")
    op.execute("DROP TABLE IF EXISTS workspace_saved_views")
