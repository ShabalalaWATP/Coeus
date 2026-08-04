"""add organisation membership lifecycle commands

Revision ID: 20260803_0023
Revises: 20260803_0022
Create Date: 2026-08-03
"""

from collections.abc import Sequence

from alembic import op

from coeus.persistence.organisation_membership_schema import (
    organisation_membership_schema_statements,
)

revision: str = "20260803_0023"
down_revision: str | None = "20260803_0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
__all__ = ("branch_labels", "depends_on", "down_revision", "downgrade", "revision", "upgrade")


def upgrade() -> None:
    for statement in organisation_membership_schema_statements():
        op.execute(statement)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS organisation_membership_commands")
