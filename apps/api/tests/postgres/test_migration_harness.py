"""Exercise Alembic against disposable real PostgreSQL databases."""

import json
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

API_ROOT = Path(__file__).resolve().parents[2]
HEAD_REVISION = "20260713_0011"

pytestmark = pytest.mark.postgres


def _alembic(database_url: str) -> Config:
    config = Config(str(API_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def _revision(database_url: str) -> str:
    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            return str(
                connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
            )
    finally:
        engine.dispose()


def test_empty_database_upgrades_to_head(postgres_database_url: str) -> None:
    command.upgrade(_alembic(postgres_database_url), "head")

    engine = create_engine(postgres_database_url)
    try:
        tables = set(inspect(engine).get_table_names())
        with engine.connect() as connection:
            extensions = set(connection.execute(text("SELECT extname FROM pg_extension")).scalars())
    finally:
        engine.dispose()

    assert _revision(postgres_database_url) == HEAD_REVISION
    assert {
        "coeus_state",
        "coeus_audit_events",
        "coeus_resource_leases",
        "coeus_ticket_aggregates",
        "coeus_outbox",
        "coeus_draft_audiences",
        "intelligence_store_products",
        "intelligence_store_assets",
    } <= tables
    assert "vector" in extensions


def test_seeded_legacy_database_upgrades_idempotently(
    postgres_database_url: str,
) -> None:
    config = _alembic(postgres_database_url)
    command.upgrade(config, "20260709_0004")
    retained = {"__type__": "coeus.domain.tickets.WorkflowPlanUpdate", "fields": {}}
    retired = {"__type__": "coeus.domain.tickets.ProjectPlanUpdate", "fields": {}}
    payload = {"records": [retained, retired]}
    engine = create_engine(postgres_database_url)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "CREATE TABLE coeus_state (namespace text PRIMARY KEY, payload jsonb NOT NULL, "
                    "updated_at timestamptz NOT NULL DEFAULT now())"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO coeus_state(namespace, payload) "
                    "VALUES ('tickets', CAST(:payload AS jsonb))"
                ),
                {"payload": json.dumps(payload)},
            )
        command.upgrade(config, "head")
        command.upgrade(config, "head")
        with engine.connect() as connection:
            cleaned = connection.execute(
                text("SELECT payload FROM coeus_state WHERE namespace = 'tickets'")
            ).scalar_one()
    finally:
        engine.dispose()

    assert cleaned == {"records": [retained]}
    assert _revision(postgres_database_url) == HEAD_REVISION


def test_previous_revision_rollback_and_reupgrade_preserve_state(
    postgres_database_url: str,
) -> None:
    config = _alembic(postgres_database_url)
    command.upgrade(config, "head")
    engine = create_engine(postgres_database_url)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO coeus_state(namespace, payload) "
                    "VALUES ('tickets', '{\"count\": 1}'::jsonb)"
                )
            )
        command.downgrade(config, "20260709_0005")
        assert "coeus_audit_events" not in inspect(engine).get_table_names()
        command.upgrade(config, "head")
        with engine.connect() as connection:
            payload = connection.execute(
                text("SELECT payload FROM coeus_state WHERE namespace = 'tickets'")
            ).scalar_one()
    finally:
        engine.dispose()

    assert payload == {"count": 1}
    assert _revision(postgres_database_url) == HEAD_REVISION
