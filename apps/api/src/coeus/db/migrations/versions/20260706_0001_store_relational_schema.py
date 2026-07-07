"""add intelligence store relational schema

Revision ID: 20260706_0001
Revises:
Create Date: 2026-07-06
"""

from collections.abc import Sequence

from alembic import op

from coeus.persistence.relational_schema import store_schema_statements

revision: str = "20260706_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    if _migration_identity()[0] != "20260706_0001":
        raise RuntimeError("Unexpected Alembic revision metadata.")
    for statement in store_schema_statements():
        op.execute(statement)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_store_semantic_labels_label")
    op.execute("DROP INDEX IF EXISTS idx_store_product_acgs_acg")
    op.execute("DROP INDEX IF EXISTS idx_store_products_embedding")
    op.execute("DROP INDEX IF EXISTS idx_store_products_search_document")
    op.execute("DROP INDEX IF EXISTS idx_store_products_semantic_labels")
    op.execute("DROP INDEX IF EXISTS idx_store_products_tags")
    op.execute("DROP INDEX IF EXISTS idx_store_products_area_or_region")
    op.execute("DROP INDEX IF EXISTS idx_store_products_product_type")
    op.execute("DROP INDEX IF EXISTS idx_store_products_owner_team")
    op.execute("DROP INDEX IF EXISTS idx_store_products_status")
    op.execute("DROP TABLE IF EXISTS intelligence_store_semantic_labels")
    op.execute("DROP TABLE IF EXISTS intelligence_store_product_acgs")
    op.execute("DROP TABLE IF EXISTS intelligence_store_assets")
    op.execute("DROP TABLE IF EXISTS intelligence_store_products")


def _migration_identity() -> tuple[
    str,
    str | None,
    str | Sequence[str] | None,
    str | Sequence[str] | None,
]:
    return revision, down_revision, branch_labels, depends_on
