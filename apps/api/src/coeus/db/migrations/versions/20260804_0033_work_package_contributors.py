"""add reviewed work-package contributor commands

Revision ID: 20260804_0033
Revises: 20260803_0032
Create Date: 2026-08-04
"""

from collections.abc import Sequence

from alembic import op

from coeus.persistence.work_package_contributor_schema import (
    work_package_contributor_schema_statements,
)

revision: str = "20260804_0033"
down_revision: str | None = "20260803_0032"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
__all__ = ("branch_labels", "depends_on", "down_revision", "downgrade", "revision", "upgrade")


def upgrade() -> None:
    for statement in work_package_contributor_schema_statements():
        op.execute(statement)


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_work_package_contributor_commands_immutable "
        "ON work_package_contributor_commands"
    )
    op.execute("DROP FUNCTION IF EXISTS reject_work_package_contributor_command_mutation()")
    op.execute("DROP TABLE IF EXISTS work_package_contributor_commands")
