"""Password-free relational projection of account eligibility evidence."""

import json
from hashlib import sha256
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Connection, RowMapping

from coeus.domain.auth import RoleName, UserAccount
from coeus.domain.jioc_principals import PrincipalKind, principal_kind
from coeus.persistence.codec import decode_value


def identity_account_projection_statements() -> tuple[str, ...]:
    return (
        """
        CREATE TABLE IF NOT EXISTS identity_account_projection (
          user_id uuid PRIMARY KEY,
          is_active boolean NOT NULL,
          roles text[] NOT NULL,
          credential_version bigint NOT NULL CHECK (credential_version >= 0),
          source_hash char(64) NOT NULL,
          projected_at timestamptz NOT NULL DEFAULT now()
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_identity_account_projection_eligibility
        ON identity_account_projection(is_active, user_id)
        """,
    )


def sync_identity_account_projection(connection: Connection, payload: dict[str, Any]) -> None:
    """Replace the projection from one validated authoritative account snapshot."""
    rows = identity_projection_rows(payload)
    for row in rows:
        connection.execute(text(_UPSERT), row)
    connection.execute(
        text(_DELETE_MISSING),
        {"user_ids": [row["user_id"] for row in rows]},
    )


def identity_projection_rows(payload: dict[str, Any]) -> tuple[dict[str, object], ...]:
    raw_users = payload.get("users")
    if not isinstance(raw_users, list):
        raise ValueError("account state requires a users list")
    rows: list[dict[str, object]] = []
    seen: set[UUID] = set()
    for raw_user in raw_users:
        user = decode_value(raw_user)
        if not isinstance(user, UserAccount):
            raise ValueError("account state contains an unsupported record")
        if user.user_id in seen:
            raise ValueError("account state contains a duplicate user identifier")
        seen.add(user.user_id)
        roles = sorted(role.value for role in user.roles)
        source = json.dumps(
            {
                "credential_version": user.credential_version,
                "is_active": user.is_active,
                "roles": roles,
                "user_id": str(user.user_id),
            },
            separators=(",", ":"),
            sort_keys=True,
        )
        rows.append(
            {
                "user_id": user.user_id,
                "is_active": user.is_active,
                "roles": roles,
                "credential_version": user.credential_version,
                "source_hash": sha256(source.encode("utf-8")).hexdigest(),
            }
        )
    return tuple(sorted(rows, key=lambda row: str(row["user_id"])))


def active_analyst_role() -> str:
    return RoleName.INTELLIGENCE_ANALYST.value


# Both variants are written out in full rather than built by appending a suffix,
# so every statement this module runs is a literal a reader can check in place.
_ACCOUNT = (
    "SELECT user_id,is_active,roles,credential_version,source_hash "
    "FROM identity_account_projection WHERE user_id=:user_id"
)
_ACCOUNT_LOCKED = (
    "SELECT user_id,is_active,roles,credential_version,source_hash "
    "FROM identity_account_projection WHERE user_id=:user_id FOR UPDATE"
)


def active_human_analyst_account(
    connection: Connection, user_id: UUID, *, lock: bool
) -> RowMapping | None:
    """Return locked canonical evidence only for an active human Analyst account."""
    if principal_kind(user_id) is not PrincipalKind.HUMAN:
        return None
    query = _ACCOUNT_LOCKED if lock else _ACCOUNT
    account = (
        connection.execute(
            text(query),
            {"user_id": user_id},
        )
        .mappings()
        .first()
    )
    if account is None or not account["is_active"] or active_analyst_role() not in account["roles"]:
        return None
    return account


_UPSERT = """
INSERT INTO identity_account_projection(
  user_id,is_active,roles,credential_version,source_hash,projected_at
) VALUES (
  :user_id,:is_active,:roles,:credential_version,:source_hash,now()
)
ON CONFLICT (user_id) DO UPDATE SET
  is_active=EXCLUDED.is_active,
  roles=EXCLUDED.roles,
  credential_version=EXCLUDED.credential_version,
  source_hash=EXCLUDED.source_hash,
  projected_at=CASE
    WHEN identity_account_projection.source_hash<>EXCLUDED.source_hash THEN now()
    ELSE identity_account_projection.projected_at
  END
"""

_DELETE_MISSING = """
DELETE FROM identity_account_projection
WHERE NOT (user_id=ANY(CAST(:user_ids AS uuid[])))
"""
