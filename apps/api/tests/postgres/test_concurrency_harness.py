"""Prove the real PostgreSQL compare-and-swap test boundary."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from sqlalchemy import create_engine, text

pytestmark = pytest.mark.postgres


def test_two_connections_allow_one_versioned_writer(postgres_database_url: str) -> None:
    engine = create_engine(postgres_database_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE version_probe ("
                "id integer PRIMARY KEY, version integer NOT NULL, value text NOT NULL)"
            )
        )
        connection.execute(
            text("INSERT INTO version_probe(id, version, value) VALUES (1, 0, 'initial')")
        )
    barrier = Barrier(2)

    def update(value: str) -> int:
        with engine.begin() as connection:
            expected = connection.execute(
                text("SELECT version FROM version_probe WHERE id = 1")
            ).scalar_one()
            barrier.wait(timeout=5)
            result = connection.execute(
                text(
                    "UPDATE version_probe SET version = version + 1, value = :value "
                    "WHERE id = 1 AND version = :expected"
                ),
                {"expected": expected, "value": value},
            )
            return result.rowcount

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            rowcounts = sorted(executor.map(update, ("first", "second")))
        with engine.connect() as connection:
            final_version = connection.execute(
                text("SELECT version FROM version_probe WHERE id = 1")
            ).scalar_one()
    finally:
        engine.dispose()

    assert rowcounts == [0, 1]
    assert final_version == 1
