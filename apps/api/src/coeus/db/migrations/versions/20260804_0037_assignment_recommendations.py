"""add deterministic assignment recommendations

Revision ID: 20260804_0037
Revises: 20260804_0036
Create Date: 2026-08-04
"""

from collections.abc import Sequence

from alembic import op

from coeus.persistence.assignment_recommendation_schema import (
    assignment_recommendation_schema_statements,
)

revision: str = "20260804_0037"
down_revision: str | None = "20260804_0036"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
__all__ = ("branch_labels", "depends_on", "down_revision", "downgrade", "revision", "upgrade")


def upgrade() -> None:
    for statement in assignment_recommendation_schema_statements():
        op.execute(statement)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS assignment_recommendation_decisions")
    op.execute("DROP TABLE IF EXISTS assignment_demand_holds")
    op.execute("DROP TABLE IF EXISTS assignment_recommendation_candidates")
    op.execute("DROP TABLE IF EXISTS assignment_recommendations")
    op.execute("DROP TABLE IF EXISTS assignment_demand_estimates")
