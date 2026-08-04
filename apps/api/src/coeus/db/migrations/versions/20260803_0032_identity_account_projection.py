"""add password-free relational account projection

Revision ID: 20260803_0032
Revises: 20260803_0031
Create Date: 2026-08-03
"""

from collections.abc import Sequence

from alembic import op

from coeus.persistence.identity_account_projection import (
    identity_account_projection_statements,
)

revision: str = "20260803_0032"
down_revision: str | None = "20260803_0031"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
__all__ = ("branch_labels", "depends_on", "down_revision", "downgrade", "revision", "upgrade")


def upgrade() -> None:
    for statement in identity_account_projection_statements():
        op.execute(statement)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS identity_account_projection")
