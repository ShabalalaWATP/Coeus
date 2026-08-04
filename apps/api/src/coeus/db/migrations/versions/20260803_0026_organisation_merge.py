"""add explicit-disposition organisation merges

Revision ID: 20260803_0026
Revises: 20260803_0025
Create Date: 2026-08-03
"""

from collections.abc import Sequence

from alembic import op

from coeus.persistence.organisation_merge_schema import organisation_merge_schema_statements

revision: str = "20260803_0026"
down_revision: str | None = "20260803_0025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
__all__ = ("branch_labels", "depends_on", "down_revision", "downgrade", "revision", "upgrade")


def upgrade() -> None:
    for statement in organisation_merge_schema_statements():
        op.execute(statement)


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_team_capability_coverage_history ON team_capability_coverage"
    )
    op.execute("DROP TRIGGER IF EXISTS trg_team_delivery_profile_history ON team_delivery_profiles")
    op.execute("DROP FUNCTION IF EXISTS preserve_team_capability_coverage_history()")
    op.execute("DROP FUNCTION IF EXISTS preserve_team_delivery_profile_history()")
    op.execute("DROP TABLE IF EXISTS team_capability_coverage_history")
    op.execute("DROP TABLE IF EXISTS team_delivery_profile_history")
    op.execute("DROP FUNCTION IF EXISTS reject_organisation_history_mutation()")
    op.execute("DROP TRIGGER IF EXISTS trg_team_task_ownership_history ON team_task_ownership")
    op.execute("DROP FUNCTION IF EXISTS preserve_team_task_ownership_history()")
    op.execute("DROP TABLE IF EXISTS team_task_ownership_history")
    op.execute("DROP FUNCTION IF EXISTS reject_team_task_ownership_history_mutation()")
    op.execute("DROP TABLE IF EXISTS organisation_merge_dispositions")
    op.execute("DROP TABLE IF EXISTS organisation_merge_commands")
