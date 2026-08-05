"""add package and reservation lifecycle reconciliation

Revision ID: 20260804_0042
Revises: 20260804_0041
Create Date: 2026-08-04
"""

from collections.abc import Sequence

from alembic import op

from coeus.persistence.package_lifecycle_input_schema import package_lifecycle_input_statements
from coeus.persistence.package_lifecycle_schema import package_lifecycle_schema_statements

revision: str = "20260804_0042"
down_revision: str | None = "20260804_0041"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
__all__ = ("branch_labels", "depends_on", "down_revision", "downgrade", "revision", "upgrade")


def upgrade() -> None:
    for statement in package_lifecycle_schema_statements():
        op.execute(statement)
    for statement in package_lifecycle_input_statements():
        op.execute(statement)


def downgrade() -> None:
    for statement in (
        "DROP TRIGGER IF EXISTS trg_predecessor_cancellation_commands_immutable "
        "ON predecessor_cancellation_commands",
        "DROP TRIGGER IF EXISTS trg_calendar_exception_package_reconciliation "
        "ON calendar_event_exceptions",
        "DROP TRIGGER IF EXISTS trg_calendar_package_reconciliation ON calendar_events",
        "DROP TRIGGER IF EXISTS trg_capability_package_reconciliation ON team_capability_coverage",
        "DROP TRIGGER IF EXISTS trg_competency_package_reconciliation ON assignment_competencies",
        "DROP TRIGGER IF EXISTS trg_team_package_reconciliation ON organisation_units",
        "DROP TRIGGER IF EXISTS trg_ticket_package_reconciliation ON coeus_ticket_aggregates",
        "DROP TRIGGER IF EXISTS trg_membership_package_reconciliation ON team_memberships",
        "DROP TRIGGER IF EXISTS trg_account_package_reconciliation ON identity_account_projection",
        "DROP TRIGGER IF EXISTS trg_package_plan_input_changed ON canonical_work_packages",
        "DROP TRIGGER IF EXISTS trg_package_terminal_reconciliation ON canonical_work_packages",
        "DROP TRIGGER IF EXISTS trg_package_predecessor_cancellation ON canonical_work_packages",
        "DROP FUNCTION IF EXISTS calendar_package_reconciliation()",
        "DROP FUNCTION IF EXISTS capability_package_reconciliation()",
        "DROP FUNCTION IF EXISTS competency_package_reconciliation()",
        "DROP FUNCTION IF EXISTS team_package_reconciliation()",
        "DROP FUNCTION IF EXISTS package_plan_input_changed()",
        "DROP FUNCTION IF EXISTS ticket_package_reconciliation()",
        "DROP FUNCTION IF EXISTS membership_package_reconciliation()",
        "DROP FUNCTION IF EXISTS account_package_reconciliation()",
        "DROP FUNCTION IF EXISTS reconcile_ineligible_participant(uuid,text,text)",
        "DROP FUNCTION IF EXISTS reconcile_terminal_package()",
        "DROP FUNCTION IF EXISTS guard_predecessor_cancellation()",
        "DROP FUNCTION IF EXISTS reject_package_lifecycle_evidence_mutation()",
    ):
        op.execute(statement)
    op.execute("DROP TABLE predecessor_cancellation_commands")
    op.execute("DROP TABLE package_lifecycle_conflicts")
    op.execute("ALTER TABLE capacity_reservations DROP COLUMN participant_role")
