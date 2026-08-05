"""add fail-closed organisation deactivation

Revision ID: 20260803_0025
Revises: 20260803_0024
Create Date: 2026-08-03
"""

from collections.abc import Sequence

from alembic import op

from coeus.persistence.organisation_deactivation_schema import (
    organisation_deactivation_schema_statements,
)

revision: str = "20260803_0025"
down_revision: str | None = "20260803_0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
__all__ = ("branch_labels", "depends_on", "down_revision", "downgrade", "revision", "upgrade")


def upgrade() -> None:
    for statement in organisation_deactivation_schema_statements():
        op.execute(statement)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS organisation_deactivation_commands")
