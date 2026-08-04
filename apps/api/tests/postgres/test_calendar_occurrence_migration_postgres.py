"""Real PostgreSQL migration proof for occurrence command replay evidence."""

from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import DBAPIError

pytestmark = pytest.mark.postgres
API_ROOT = Path(__file__).resolve().parents[2]


def _config(database_url: str) -> Config:
    config = Config(str(API_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def test_occurrence_command_upgrade_round_trips_without_new_evidence(
    postgres_database_url: str,
) -> None:
    config = _config(postgres_database_url)
    command.upgrade(config, "20260804_0037")
    command.upgrade(config, "20260804_0038")
    engine = create_engine(postgres_database_url)
    try:
        columns = {item["name"] for item in inspect(engine).get_columns("calendar_event_commands")}
        assert "future_event_id" in columns
        command.downgrade(config, "20260804_0037")
        columns = {item["name"] for item in inspect(engine).get_columns("calendar_event_commands")}
        assert "future_event_id" not in columns
        command.upgrade(config, "20260804_0038")
    finally:
        engine.dispose()


def test_occurrence_command_downgrade_refuses_replay_evidence_atomically(
    postgres_database_url: str,
) -> None:
    config = _config(postgres_database_url)
    command.upgrade(config, "20260804_0038")
    engine = create_engine(postgres_database_url)
    event_id, actor_id = uuid4(), uuid4()
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO calendar_events(event_id,owner_user_id,source,activity_category,"
                    "all_day_start,all_day_end,time_zone,availability_effect,privacy_level,note,"
                    "status,created_by_user_id,version) VALUES (:event,:actor,'personal','leave',"
                    "DATE '2026-08-10',DATE '2026-08-11','Europe/London','unavailable',"
                    "'private','', 'active',:actor,2)"
                ),
                {"event": event_id, "actor": actor_id},
            )
            connection.execute(
                text(
                    "INSERT INTO calendar_event_commands(command_id,actor_user_id,idempotency_key,"
                    "command_type,request_hash,event_id,result_version) VALUES "
                    "(:command,:actor,'cancel-one','cancel_occurrence',:hash,:event,2)"
                ),
                {
                    "command": uuid4(),
                    "actor": actor_id,
                    "hash": "a" * 64,
                    "event": event_id,
                },
            )
        with pytest.raises(DBAPIError, match="occurrence commands require revision 0038"):
            command.downgrade(config, "20260804_0037")
        with engine.connect() as connection:
            revision = connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one()
            evidence = connection.execute(
                text("SELECT command_type FROM calendar_event_commands")
            ).scalar_one()
        assert revision == "20260804_0038" and evidence == "cancel_occurrence"
        assert "future_event_id" in {
            item["name"] for item in inspect(engine).get_columns("calendar_event_commands")
        }
    finally:
        engine.dispose()
