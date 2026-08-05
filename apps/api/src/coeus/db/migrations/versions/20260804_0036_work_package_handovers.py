"""add canonical work-package handover commands

Revision ID: 20260804_0036
Revises: 20260804_0035
Create Date: 2026-08-04
"""

from collections.abc import Sequence

from alembic import op

from coeus.persistence.work_package_handover_schema import (
    work_package_handover_schema_statements,
)

revision: str = "20260804_0036"
down_revision: str | None = "20260804_0035"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
__all__ = ("branch_labels", "depends_on", "down_revision", "downgrade", "revision", "upgrade")


def upgrade() -> None:
    op.execute(
        "ALTER TABLE capacity_reservations DROP CONSTRAINT IF EXISTS "
        "capacity_reservations_idempotency_key_key"
    )
    op.execute(
        """
        DO $$ BEGIN
          IF NOT EXISTS (
            SELECT 1 FROM pg_constraint
            WHERE conrelid='capacity_reservations'::regclass
              AND conname='uq_capacity_reservation_actor_key'
          ) THEN
            ALTER TABLE capacity_reservations ADD CONSTRAINT
              uq_capacity_reservation_actor_key UNIQUE(actor_user_id,idempotency_key);
          END IF;
        END $$
        """
    )
    for statement in work_package_handover_schema_statements():
        op.execute(statement)


def downgrade() -> None:
    op.execute(
        """
        DO $$ BEGIN
          IF EXISTS (
            SELECT 1 FROM capacity_reservations
            GROUP BY idempotency_key
            HAVING count(DISTINCT actor_user_id) > 1
          ) THEN
            RAISE EXCEPTION USING
              ERRCODE='check_violation',
              MESSAGE='0036 downgrade cannot represent actor-scoped capacity keys',
              HINT='Keep 0036 or restore a pre-0036 backup; never rewrite idempotency evidence.';
          END IF;
        END $$
        """
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_work_package_handover_commands_immutable "
        "ON work_package_handover_commands"
    )
    op.execute("DROP FUNCTION IF EXISTS reject_work_package_handover_command_mutation()")
    op.execute("DROP TABLE IF EXISTS work_package_handover_commands")
    op.execute(
        "ALTER TABLE capacity_reservations DROP CONSTRAINT IF EXISTS "
        "uq_capacity_reservation_actor_key"
    )
    op.execute(
        "ALTER TABLE capacity_reservations ADD CONSTRAINT "
        "capacity_reservations_idempotency_key_key UNIQUE(idempotency_key)"
    )
