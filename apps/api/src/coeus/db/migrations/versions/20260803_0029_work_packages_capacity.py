"""add canonical work packages and capacity reservations

Revision ID: 20260803_0029
Revises: 20260803_0028
Create Date: 2026-08-03
"""

from collections.abc import Sequence

from alembic import op

from coeus.persistence.work_package_schema import work_package_schema_statements

revision: str = "20260803_0029"
down_revision: str | None = "20260803_0028"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
__all__ = ("branch_labels", "depends_on", "down_revision", "downgrade", "revision", "upgrade")


def upgrade() -> None:
    for statement in work_package_schema_statements():
        op.execute(statement)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_work_package_history_immutable ON work_package_history")
    op.execute("DROP FUNCTION IF EXISTS reject_work_package_history_mutation()")
    for table_name in (
        "work_package_commands",
        "work_package_history",
        "capacity_reservations",
        "work_package_dependencies",
        "work_package_participants",
        "canonical_work_packages",
        "capacity_exceptions",
        "working_patterns",
    ):
        op.execute(f"DROP TABLE IF EXISTS {table_name}")
