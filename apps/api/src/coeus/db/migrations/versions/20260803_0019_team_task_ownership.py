"""add canonical team task ownership

Revision ID: 20260803_0019
Revises: 20260803_0018
Create Date: 2026-08-03
"""

from collections.abc import Sequence

from alembic import op

from coeus.persistence.team_task_ownership_schema import (
    team_task_ownership_schema_statements,
)

revision: str = "20260803_0019"
down_revision: str | None = "20260803_0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
__all__ = ("branch_labels", "depends_on", "down_revision", "downgrade", "revision", "upgrade")


def upgrade() -> None:
    for statement in team_task_ownership_schema_statements():
        op.execute(statement)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS team_task_ownership")
