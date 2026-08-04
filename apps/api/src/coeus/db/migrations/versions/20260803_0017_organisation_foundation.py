"""add disabled relational organisation foundation

Revision ID: 20260803_0017
Revises: 20260801_0016
Create Date: 2026-08-03
"""

from collections.abc import Sequence

from alembic import op

from coeus.persistence.organisation_schema import organisation_schema_statements

revision: str = "20260803_0017"
down_revision: str | None = "20260801_0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
__all__ = ("branch_labels", "depends_on", "down_revision", "downgrade", "revision", "upgrade")


def upgrade() -> None:
    for statement in organisation_schema_statements():
        op.execute(statement)


def downgrade() -> None:
    for table_name in (
        "organisation_reconciliation_findings",
        "organisation_reconciliation_checkpoints",
        "effective_authority_epochs",
        "team_management_grants",
        "team_memberships",
        "team_capability_coverage",
        "team_delivery_profiles",
        "organisation_topology_revisions",
        "organisation_unit_closure",
        "organisation_units",
    ):
        op.execute(f"DROP TABLE IF EXISTS {table_name}")
    for function_name in (
        "validate_organisation_topology_revision_insert",
        "validate_organisation_closure_write",
        "validate_organisation_unit_tree_integrity",
        "reject_organisation_topology_revision_mutation",
    ):
        op.execute(f"DROP FUNCTION IF EXISTS {function_name}()")
