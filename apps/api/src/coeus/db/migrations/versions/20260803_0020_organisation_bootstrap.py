"""add one-shot organisation bootstrap state

Revision ID: 20260803_0020
Revises: 20260803_0019
Create Date: 2026-08-03
"""

from collections.abc import Sequence

from alembic import op

from coeus.persistence.organisation_bootstrap_schema import (
    organisation_bootstrap_schema_statements,
)

revision: str = "20260803_0020"
down_revision: str | None = "20260803_0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
__all__ = ("branch_labels", "depends_on", "down_revision", "downgrade", "revision", "upgrade")


def upgrade() -> None:
    for statement in organisation_bootstrap_schema_statements():
        op.execute(statement)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS organisation_bootstrap_state")
