"""add verified assignment competencies

Revision ID: 20260803_0031
Revises: 20260803_0030
Create Date: 2026-08-03
"""

from collections.abc import Sequence

from alembic import op

from coeus.persistence.workforce_competency_schema import (
    workforce_competency_schema_statements,
)

revision: str = "20260803_0031"
down_revision: str | None = "20260803_0030"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
__all__ = ("branch_labels", "depends_on", "down_revision", "downgrade", "revision", "upgrade")


def upgrade() -> None:
    for statement in workforce_competency_schema_statements():
        op.execute(statement)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS assignment_competencies")
