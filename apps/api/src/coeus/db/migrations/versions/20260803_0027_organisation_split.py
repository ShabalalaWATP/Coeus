"""add explicit-mapping organisation splits

Revision ID: 20260803_0027
Revises: 20260803_0026
Create Date: 2026-08-03
"""

from collections.abc import Sequence

from alembic import op

from coeus.persistence.organisation_merge_topology_schema import (
    merge_topology_guard_statement,
)
from coeus.persistence.organisation_split_schema import organisation_split_schema_statements

revision: str = "20260803_0027"
down_revision: str | None = "20260803_0026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
__all__ = ("branch_labels", "depends_on", "down_revision", "downgrade", "revision", "upgrade")


def upgrade() -> None:
    for statement in organisation_split_schema_statements():
        op.execute(statement)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS organisation_split_dispositions")
    op.execute("DROP TABLE IF EXISTS organisation_split_commands")
    op.execute(merge_topology_guard_statement())
