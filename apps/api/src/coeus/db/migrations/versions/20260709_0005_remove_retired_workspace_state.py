"""remove retired workspace state payloads

Revision ID: 20260709_0005
Revises: 20260709_0004
Create Date: 2026-07-09
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any

from alembic import op
from sqlalchemy import text

revision: str = "20260709_0005"
down_revision: str | None = "20260709_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_RETIRED_PERMISSION_VALUES = frozenset(
    {
        "project:add_member",
        "project:create",
        "project:read",
        "project:remove_member",
        "project:update",
    }
)
_RETIRED_TYPES = frozenset(
    {
        "coeus.domain.access.ProjectMember",
        "coeus.domain.access.ProjectMilestone",
        "coeus.domain.access.ProjectPlanItem",
        "coeus.domain.access.ProjectWorkspace",
        "coeus.domain.tickets.ProjectPlanUpdate",
    }
)
_DROP = object()


def upgrade() -> None:
    connection = op.get_bind()
    rows = connection.execute(text("SELECT namespace, payload FROM coeus_state")).mappings()
    for row in rows:
        payload = row["payload"]
        cleaned = _clean_payload(payload)
        if cleaned is not _DROP and cleaned != payload:
            connection.execute(
                text(
                    """
                    UPDATE coeus_state
                    SET payload = CAST(:payload AS jsonb), updated_at = now()
                    WHERE namespace = :namespace
                    """
                ),
                {
                    "namespace": row["namespace"],
                    "payload": json.dumps(cleaned),
                },
            )


def downgrade() -> None:
    """Retired workspace state cleanup is intentionally one-way."""


def _clean_payload(value: Any) -> Any:
    if isinstance(value, list):
        return [cleaned for item in value if (cleaned := _clean_payload(item)) is not _DROP]
    if not isinstance(value, Mapping):
        return value
    if _is_retired_payload(value):
        return _DROP
    return {
        str(key): cleaned
        for key, item in value.items()
        if (cleaned := _clean_payload(item)) is not _DROP
    }


def _is_retired_payload(value: Mapping[str, Any]) -> bool:
    if str(value.get("__type__")) in _RETIRED_TYPES:
        return True
    return (
        value.get("__enum__") == "coeus.core.permissions.Permission"
        and value.get("value") in _RETIRED_PERMISSION_VALUES
    )
