"""release capacity for outcome-loop closures

Revision ID: 20260727_0015
Revises: 20260720_0014
Create Date: 2026-07-27
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260727_0015"
down_revision: str | None = "20260720_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
__all__ = ("branch_labels", "depends_on", "down_revision", "downgrade", "revision", "upgrade")

# CLOSED_REQUIREMENT_MET, CLOSED_REANALYSIS_DECLINED, CLOSED_UNANSWERED and
# CLOSED_JOINED_EXISTING_WORK were added to the lifecycle after the capacity
# projection was introduced, so their rows were projected as still consuming
# admission capacity. They are terminal and must release capacity.


def upgrade() -> None:
    op.execute(
        "UPDATE coeus_ticket_aggregates SET consumes_capacity = false "
        "WHERE consumes_capacity AND state IN ("
        "'CLOSED_JOINED_EXISTING_WORK', 'CLOSED_REANALYSIS_DECLINED', "
        "'CLOSED_REQUIREMENT_MET', 'CLOSED_UNANSWERED')"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE coeus_ticket_aggregates SET consumes_capacity = true "
        "WHERE NOT consumes_capacity AND state IN ("
        "'CLOSED_JOINED_EXISTING_WORK', 'CLOSED_REANALYSIS_DECLINED', "
        "'CLOSED_REQUIREMENT_MET', 'CLOSED_UNANSWERED')"
    )
