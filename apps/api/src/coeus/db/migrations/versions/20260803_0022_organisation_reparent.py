"""add safe organisation reparent commands

Revision ID: 20260803_0022
Revises: 20260803_0021
Create Date: 2026-08-03
"""

from collections.abc import Sequence

from alembic import op

from coeus.persistence.organisation_reparent_schema import (
    organisation_reparent_schema_statements,
)
from coeus.persistence.organisation_topology_sql import topology_integrity_statements

revision: str = "20260803_0022"
down_revision: str | None = "20260803_0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
__all__ = ("branch_labels", "depends_on", "down_revision", "downgrade", "revision", "upgrade")


def upgrade() -> None:
    for statement in organisation_reparent_schema_statements():
        op.execute(statement)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS organisation_reparent_commands")
    for statement in topology_integrity_statements():
        op.execute(statement)
