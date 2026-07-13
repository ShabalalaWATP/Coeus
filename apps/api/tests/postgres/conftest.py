"""Isolated real-PostgreSQL fixtures for migration and concurrency gates."""

import os
from collections.abc import Iterator
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql
from sqlalchemy.engine import make_url


@pytest.fixture
def postgres_database_url() -> Iterator[str]:
    """Create a disposable database and return its synchronous SQLAlchemy URL."""

    configured = os.getenv("COEUS_TEST_DATABASE_URL")
    if not configured:
        pytest.skip("COEUS_TEST_DATABASE_URL is not configured")
    base_url = make_url(configured)
    database_name = f"coeus_test_{uuid4().hex}"
    admin_url = base_url.set(drivername="postgresql", database="postgres")
    admin_dsn = admin_url.render_as_string(hide_password=False)
    with psycopg.connect(admin_dsn, autocommit=True) as connection:
        connection.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database_name)))
    test_url = base_url.set(database=database_name).render_as_string(hide_password=False)
    try:
        yield test_url
    finally:
        with psycopg.connect(admin_dsn, autocommit=True) as connection:
            connection.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname = %s AND pid <> pg_backend_pid()",
                (database_name,),
            )
            connection.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(database_name)))
