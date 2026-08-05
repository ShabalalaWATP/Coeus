"""add non-authoritative workspace Store links

Revision ID: 20260804_0043
Revises: 20260804_0042
Create Date: 2026-08-04
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260804_0043"
down_revision: str | None = "20260804_0042"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
__all__ = ("branch_labels", "depends_on", "down_revision", "downgrade", "revision", "upgrade")


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS workspace_store_links (
          link_id uuid PRIMARY KEY,
          owner_user_id uuid NOT NULL,
          unit_id uuid NOT NULL REFERENCES organisation_units(unit_id) ON DELETE RESTRICT,
          source_type text NOT NULL CHECK (source_type IN ('ticket','work_package')),
          source_id uuid NOT NULL,
          target_type text NOT NULL CHECK (target_type IN ('project','product')),
          target_id uuid NOT NULL,
          label text NOT NULL CHECK (char_length(label) BETWEEN 1 AND 160),
          version bigint NOT NULL DEFAULT 1 CHECK (version > 0),
          created_at timestamptz NOT NULL,
          updated_at timestamptz NOT NULL,
          UNIQUE(source_type,source_id,target_type,target_id)
        );
        CREATE INDEX IF NOT EXISTS idx_workspace_store_links_source_page
        ON workspace_store_links(unit_id,source_type,source_id,link_id)
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS workspace_store_links")
