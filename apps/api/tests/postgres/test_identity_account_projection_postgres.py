"""Real PostgreSQL evidence for transactionally projected account eligibility."""

from dataclasses import replace

import pytest
from sqlalchemy import create_engine, text

from coeus.core.config import Settings
from coeus.domain.auth import RoleName
from coeus.persistence.state_store import PostgresStateStore
from coeus.repositories.auth import SeedUserRepository
from coeus.services.passwords import PasswordHasher

pytestmark = pytest.mark.postgres


def test_account_save_projects_current_eligibility_without_credentials(
    postgres_database_url: str,
) -> None:
    settings = Settings(
        environment="test",
        database_url=postgres_database_url,
        argon2_memory_cost=8_192,
    )
    state = PostgresStateStore(postgres_database_url, "relational")
    users = SeedUserRepository(settings, PasswordHasher(settings), state)
    analyst = next(
        user for user in users.list_users() if RoleName.INTELLIGENCE_ANALYST in user.roles
    )
    engine = create_engine(postgres_database_url)
    with engine.connect() as connection:
        row = connection.execute(
            text(
                "SELECT is_active,roles,credential_version FROM identity_account_projection "
                "WHERE user_id=:user_id"
            ),
            {"user_id": analyst.user_id},
        ).one()
        columns = {item["column_name"] for item in connection.execute(text(_COLUMNS)).mappings()}
    assert row.is_active
    assert RoleName.INTELLIGENCE_ANALYST.value in row.roles
    assert row.credential_version == analyst.credential_version
    assert {"username", "display_name", "password_hash"}.isdisjoint(columns)

    users.save(replace(analyst, is_active=False, credential_version=5))
    with engine.connect() as connection:
        changed = connection.execute(
            text(
                "SELECT is_active,credential_version FROM identity_account_projection "
                "WHERE user_id=:user_id"
            ),
            {"user_id": analyst.user_id},
        ).one()
    assert not changed.is_active
    assert changed.credential_version == 5


_COLUMNS = """
SELECT column_name FROM information_schema.columns
WHERE table_schema=current_schema() AND table_name='identity_account_projection'
"""
