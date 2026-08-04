"""add reviewed cross-team workflow-leg transfers

Revision ID: 20260804_0039
Revises: 20260804_0038
Create Date: 2026-08-04
"""

from collections.abc import Sequence

from alembic import op

from coeus.persistence.workflow_leg_transfer_schema import workflow_leg_transfer_schema_statements

revision: str = "20260804_0039"
down_revision: str | None = "20260804_0038"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
__all__ = ("branch_labels", "depends_on", "down_revision", "downgrade", "revision", "upgrade")


def upgrade() -> None:
    for statement in workflow_leg_transfer_schema_statements():
        op.execute(statement)


def downgrade() -> None:
    op.execute(
        "DO $$ BEGIN IF EXISTS(SELECT 1 FROM workflow_leg_transfers) THEN "
        "RAISE EXCEPTION 'cannot remove workflow-leg transfer evidence' USING ERRCODE='23514'; "
        "END IF; END $$"
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_workflow_leg_transfer_proposal_protected "
        "ON workflow_leg_transfers"
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_workflow_leg_transfer_commands_immutable "
        "ON workflow_leg_transfer_commands"
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_workflow_leg_transfer_packages_immutable "
        "ON workflow_leg_transfer_packages"
    )
    op.execute("DROP FUNCTION IF EXISTS reject_workflow_leg_transfer_evidence_mutation()")
    op.execute("DROP FUNCTION IF EXISTS protect_workflow_leg_transfer_proposal()")
    op.execute("DROP TABLE IF EXISTS workflow_leg_transfer_commands")
    op.execute("DROP TABLE IF EXISTS workflow_leg_transfer_team_holds")
    op.execute("DROP TABLE IF EXISTS workflow_leg_transfer_packages")
    op.execute("DROP TABLE IF EXISTS workflow_leg_transfers")
