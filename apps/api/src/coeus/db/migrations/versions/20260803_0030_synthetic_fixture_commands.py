"""add synthetic organisation fixture commands

Revision ID: 20260803_0030
Revises: 20260803_0029
Create Date: 2026-08-03
"""

from collections.abc import Sequence

from alembic import op

from coeus.persistence.synthetic_fixture_schema import synthetic_fixture_schema_statements

revision: str = "20260803_0030"
down_revision: str | None = "20260803_0029"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
__all__ = ("branch_labels", "depends_on", "down_revision", "downgrade", "revision", "upgrade")


def upgrade() -> None:
    for statement in synthetic_fixture_schema_statements():
        op.execute(statement)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS synthetic_organisation_fixture_commands")
