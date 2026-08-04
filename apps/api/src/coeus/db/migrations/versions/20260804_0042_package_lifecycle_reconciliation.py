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
    for table, trigger in (
        (
            "predecessor_cancellation_commands",
            "trg_predecessor_cancellation_commands_immutable",
        ),
        ("calendar_event_exceptions", "trg_calendar_exception_package_reconciliation"),
        ("calendar_events", "trg_calendar_package_reconciliation"),
        ("team_capability_coverage", "trg_capability_package_reconciliation"),
        ("assignment_competencies", "trg_competency_package_reconciliation"),
        ("organisation_units", "trg_team_package_reconciliation"),
        ("coeus_ticket_aggregates", "trg_ticket_package_reconciliation"),
        ("team_memberships", "trg_membership_package_reconciliation"),
        ("identity_account_projection", "trg_account_package_reconciliation"),
        ("canonical_work_packages", "trg_package_plan_input_changed"),
        ("canonical_work_packages", "trg_package_terminal_reconciliation"),
        ("canonical_work_packages", "trg_package_predecessor_cancellation"),
    ):
        op.execute(f"DROP TRIGGER IF EXISTS {trigger} ON {table}")
    for function in (
        "calendar_package_reconciliation",
        "capability_package_reconciliation",
        "competency_package_reconciliation",
        "team_package_reconciliation",
        "package_plan_input_changed",
        "ticket_package_reconciliation",
        "membership_package_reconciliation",
        "account_package_reconciliation",
        "reconcile_ineligible_participant",
        "reconcile_terminal_package",
        "guard_predecessor_cancellation",
        "reject_package_lifecycle_evidence_mutation",
    ):
        suffix = "(uuid,text,text)" if function == "reconcile_ineligible_participant" else "()"
        op.execute(f"DROP FUNCTION IF EXISTS {function}{suffix}")
    op.execute("DROP TABLE predecessor_cancellation_commands")
    op.execute("DROP TABLE package_lifecycle_conflicts")
    op.execute("ALTER TABLE capacity_reservations DROP COLUMN participant_role")
