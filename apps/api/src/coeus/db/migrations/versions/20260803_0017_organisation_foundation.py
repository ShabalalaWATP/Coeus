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
    for statement in (
        "DROP TABLE IF EXISTS organisation_reconciliation_findings",
        "DROP TABLE IF EXISTS organisation_reconciliation_checkpoints",
        "DROP TABLE IF EXISTS effective_authority_epochs",
        "DROP TABLE IF EXISTS team_management_grants",
        "DROP TABLE IF EXISTS team_memberships",
        "DROP TABLE IF EXISTS team_capability_coverage",
        "DROP TABLE IF EXISTS team_delivery_profiles",
        "DROP TABLE IF EXISTS organisation_topology_revisions",
        "DROP TABLE IF EXISTS organisation_unit_closure",
        "DROP TABLE IF EXISTS organisation_units",
        "DROP FUNCTION IF EXISTS validate_organisation_topology_revision_insert()",
        "DROP FUNCTION IF EXISTS validate_organisation_closure_write()",
        "DROP FUNCTION IF EXISTS validate_organisation_unit_tree_integrity()",
        "DROP FUNCTION IF EXISTS reject_organisation_topology_revision_mutation()",
    ):
        op.execute(statement)
