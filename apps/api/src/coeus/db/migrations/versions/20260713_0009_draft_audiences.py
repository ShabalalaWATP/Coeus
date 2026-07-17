"""add indexed draft audience projection

Revision ID: 20260713_0009
Revises: 20260713_0008
Create Date: 2026-07-13
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260713_0009"
down_revision: str | None = "20260713_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
__all__ = ("branch_labels", "depends_on", "down_revision", "downgrade", "revision", "upgrade")


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS coeus_draft_audiences (
            product_id uuid NOT NULL,
            principal_id uuid NOT NULL,
            reason text NOT NULL,
            ticket_id uuid NOT NULL,
            updated_at timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY(product_id, principal_id, reason, ticket_id)
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_coeus_draft_audiences_principal "
        "ON coeus_draft_audiences(principal_id, product_id, reason)"
    )
    op.execute(
        """
        INSERT INTO coeus_draft_audiences(product_id, principal_id, reason, ticket_id)
        SELECT
          (link -> 'fields' -> 'product_id' ->> '__uuid__')::uuid,
          (assignment -> 'fields' -> 'analyst_user_id' ->> '__uuid__')::uuid,
          'assigned_analyst',
          aggregate.ticket_id
        FROM coeus_ticket_aggregates AS aggregate
        CROSS JOIN LATERAL jsonb_array_elements(
          aggregate.payload -> 'fields' -> 'linked_products' -> '__tuple__'
        ) AS link
        CROSS JOIN LATERAL jsonb_array_elements(
          aggregate.payload -> 'fields' -> 'analyst_assignments' -> '__tuple__'
        ) AS assignment
        WHERE COALESCE((assignment -> 'fields' ->> 'active')::boolean, true)
        ON CONFLICT DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO coeus_draft_audiences(product_id, principal_id, reason, ticket_id)
        SELECT
          (link -> 'fields' -> 'product_id' ->> '__uuid__')::uuid,
          (assignment -> 'fields' -> 'assigned_by_user_id' ->> '__uuid__')::uuid,
          'responsible_manager',
          aggregate.ticket_id
        FROM coeus_ticket_aggregates AS aggregate
        CROSS JOIN LATERAL jsonb_array_elements(
          aggregate.payload -> 'fields' -> 'linked_products' -> '__tuple__'
        ) AS link
        CROSS JOIN LATERAL jsonb_array_elements(
          aggregate.payload -> 'fields' -> 'analyst_assignments' -> '__tuple__'
        ) AS assignment
        WHERE COALESCE((assignment -> 'fields' ->> 'active')::boolean, true)
        ON CONFLICT DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE coeus_draft_audiences")
