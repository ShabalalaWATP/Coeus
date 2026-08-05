"""add disabled organisation grant authority

Revision ID: 20260803_0018
Revises: 20260803_0017
Create Date: 2026-08-03
"""

from collections.abc import Sequence

from alembic import op

from coeus.persistence.organisation_authority_schema import (
    organisation_authority_schema_statements,
)

revision: str = "20260803_0018"
down_revision: str | None = "20260803_0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
__all__ = ("branch_labels", "depends_on", "down_revision", "downgrade", "revision", "upgrade")


def upgrade() -> None:
    op.execute(
        "ALTER TABLE organisation_units ADD COLUMN IF NOT EXISTS provenance text "
        "NOT NULL DEFAULT 'manual' CHECK (char_length(provenance) BETWEEN 1 AND 120)"
    )
    op.execute(
        "ALTER TABLE team_delivery_profiles ADD COLUMN IF NOT EXISTS provenance text "
        "NOT NULL DEFAULT 'manual' CHECK (char_length(provenance) BETWEEN 1 AND 120)"
    )
    for statement in organisation_authority_schema_statements():
        op.execute(statement)


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_organisation_grant_lineage_immutable ON team_management_grants"
    )
    op.execute("DROP FUNCTION IF EXISTS reject_organisation_grant_lineage_mutation()")
    op.execute("DROP TABLE IF EXISTS organisation_grant_commands")
    op.execute("ALTER TABLE team_management_grants DROP COLUMN IF EXISTS revocation_reason")
    op.execute("ALTER TABLE team_management_grants DROP COLUMN IF EXISTS revoked_by_user_id")
