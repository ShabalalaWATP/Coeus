"""Disposable database and synthetic fixture helpers for recovery tests."""

from collections.abc import Iterator
from contextlib import contextmanager
from uuid import UUID, uuid4

import psycopg
from alembic import command
from alembic.config import Config
from backup_restore_follow_on_support import seed_follow_on_recovery_rows
from psycopg import sql
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from coeus.domain.synthetic_organisation_fixture import (
    SyntheticFixtureCommand,
    SyntheticFixtureUser,
)
from coeus.persistence.synthetic_organisation_fixture_postgres import (
    PostgresSyntheticOrganisationFixtureStore,
)
from coeus.repositories.auth_seed import seed_user_specs
from coeus.repositories.synthetic_organisation_manifest import synthetic_posting_specs
from coeus.repositories.synthetic_workforce import synthetic_user_id


def seed_fixture(database_url: str) -> UUID:
    upgrade_database(database_url)
    engine = create_engine(database_url)
    active = {item.username: item.is_active for item in seed_user_specs()}
    users = tuple(
        SyntheticFixtureUser(username, synthetic_user_id(username), active[username])
        for username in dict.fromkeys(item.username for item in synthetic_posting_specs())
    )
    actor_id = synthetic_user_id("admin@example.test")
    store = PostgresSyntheticOrganisationFixtureStore(engine)
    preview = store.preview(actor_id, users)
    store.apply(
        SyntheticFixtureCommand(uuid4(), f"backup-{uuid4()}", actor_id, preview.preview_hash), users
    )
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO identity_account_projection"
                "(user_id,is_active,roles,credential_version,source_hash) "
                "VALUES (:actor,true,ARRAY['system_admin'],0,:digest)"
            ),
            {"actor": actor_id, "digest": "a" * 64},
        )
        seed_follow_on_recovery_rows(connection, actor_id)
    return actor_id


@contextmanager
def second_database(database_url: str) -> Iterator[str]:
    base = make_url(database_url)
    name = f"coeus_sprint24_restore_{uuid4().hex}"
    admin_url = base.set(drivername="postgresql", database="postgres")
    admin_dsn = admin_url.render_as_string(hide_password=False)
    with psycopg.connect(admin_dsn, autocommit=True) as connection:
        connection.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    target = base.set(database=name).render_as_string(hide_password=False)
    try:
        yield target
    finally:
        with psycopg.connect(admin_dsn, autocommit=True) as connection:
            connection.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname=%s AND pid<>pg_backend_pid()",
                (name,),
            )
            connection.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


def upgrade_database(database_url: str) -> None:
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "head")


def dsn(database_url: str) -> str:
    return make_url(database_url).set(drivername="postgresql").render_as_string(hide_password=False)
