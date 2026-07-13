"""reconcile ticket aggregate canonical hashes

Revision ID: 20260713_0012
Revises: 20260713_0011
Create Date: 2026-07-13
"""

import json
from collections.abc import Sequence
from hashlib import sha256

from alembic import op
from sqlalchemy import text

from coeus.persistence.codec import decode_value, encode_value

revision: str = "20260713_0012"
down_revision: str | None = "20260713_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
__all__ = ("branch_labels", "depends_on", "down_revision", "downgrade", "revision", "upgrade")


def upgrade() -> None:
    """Replace migration-era hashes with the runtime canonical JSON digest."""
    connection = op.get_bind()
    rows = connection.execute(
        text("SELECT ticket_id, payload FROM coeus_ticket_aggregates ORDER BY ticket_id")
    ).mappings()
    for row in rows:
        payload = encode_value(decode_value(row["payload"]))
        serialised = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        canonical_hash = sha256(serialised.encode("utf-8")).hexdigest()
        connection.execute(
            text(
                "UPDATE coeus_ticket_aggregates "
                "SET payload = CAST(:payload AS jsonb), canonical_hash = :canonical_hash "
                "WHERE ticket_id = :ticket_id "
                "AND (payload <> CAST(:payload AS jsonb) OR canonical_hash <> :canonical_hash)"
            ),
            {
                "ticket_id": row["ticket_id"],
                "payload": serialised,
                "canonical_hash": canonical_hash,
            },
        )


def downgrade() -> None:
    # Runtime and rollback readers require the canonical digest. Reintroducing
    # the incompatible migration-era MD5 value would make valid rows unusable.
    pass
