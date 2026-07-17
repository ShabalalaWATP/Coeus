"""add shared resource admission leases

Revision ID: 20260713_0007
Revises: 20260710_0006
Create Date: 2026-07-13
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260713_0007"
down_revision: str | None = "20260710_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
__all__ = ("branch_labels", "depends_on", "down_revision", "downgrade", "revision", "upgrade")


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS coeus_resource_leases (
            lease_id uuid PRIMARY KEY,
            resource_type text NOT NULL,
            principal_id uuid NOT NULL,
            units bigint NOT NULL CHECK (units > 0),
            acquired_at timestamptz NOT NULL DEFAULT now(),
            expires_at timestamptz NOT NULL,
            committed boolean NOT NULL DEFAULT false,
            released_at timestamptz
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_coeus_resource_leases_scope "
        "ON coeus_resource_leases(resource_type, expires_at, principal_id)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE coeus_resource_leases")
