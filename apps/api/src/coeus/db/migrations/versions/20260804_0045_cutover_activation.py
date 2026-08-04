"""add exact-candidate organisation cutover persistence

Revision ID: 20260804_0045
Revises: 20260804_0044
Create Date: 2026-08-04
"""

from collections.abc import Sequence

from alembic import op

from coeus.persistence.cutover_activation_schema import cutover_activation_schema_statements

revision: str = "20260804_0045"
down_revision: str | None = "20260804_0044"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
__all__ = ("branch_labels", "depends_on", "down_revision", "downgrade", "revision", "upgrade")


def upgrade() -> None:
    for statement in cutover_activation_schema_statements():
        op.execute(statement)


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM organisation_cutover_slice_state WHERE status='active') THEN
            RAISE EXCEPTION 'active cutover is forward-only; downgrade is refused';
          END IF;
        END $$
        """
    )
    op.execute("DROP TRIGGER trg_coeus_state_cutover_writer_fence ON coeus_state")
    op.execute("DROP TRIGGER trg_ticket_task_capacity_writer_fence ON coeus_ticket_aggregates")
    op.execute("DROP TRIGGER trg_ticket_active_task_capacity_projection ON coeus_ticket_aggregates")
    for table in (
        "organisation_cutover_recovery_events",
        "organisation_cutover_writer_fences",
        "organisation_cutover_checkpoint_events",
        "organisation_cutover_checkpoints",
        "organisation_cutover_evidence",
        "organisation_cutover_slice_state",
        "organisation_cutover_approvals",
        "organisation_cutover_release",
        "organisation_cutover_manifests",
    ):
        op.execute(f"DROP TABLE {table}")
    op.execute("DROP FUNCTION reject_fenced_cutover_source_write()")
    op.execute("DROP FUNCTION reject_fenced_task_capacity_write()")
    op.execute("DROP FUNCTION require_active_task_capacity_projection()")
    op.execute("DROP FUNCTION reject_cutover_evidence_mutation()")
