"""Current-account projection setup for organisation PostgreSQL tests."""

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Engine


def activate_principals(engine: Engine, *principal_ids: UUID) -> None:
    _activate(engine, (), principal_ids)


def activate_analysts(engine: Engine, *principal_ids: UUID) -> None:
    _activate(engine, ("Analyst",), principal_ids)


def _activate(engine: Engine, roles: tuple[str, ...], principal_ids: tuple[UUID, ...]) -> None:
    with engine.begin() as connection:
        for principal_id in sorted(set(principal_ids), key=str):
            connection.execute(
                text(
                    "INSERT INTO identity_account_projection"
                    "(user_id,is_active,roles,credential_version,source_hash) "
                    "VALUES (:user_id,true,:roles,0,:source_hash) "
                    "ON CONFLICT (user_id) DO UPDATE SET is_active=true,roles=EXCLUDED.roles"
                ),
                {"user_id": principal_id, "roles": list(roles), "source_hash": "a" * 64},
            )
