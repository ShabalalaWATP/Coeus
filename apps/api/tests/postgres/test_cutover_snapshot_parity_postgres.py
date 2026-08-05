"""Source-to-target visibility parity evidence for every cutover slice."""

import json
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from coeus.domain.cutover_activation import CutoverSlice
from coeus.domain.teams import OrgTeam, TeamKind
from coeus.persistence.codec import encode_value
from coeus.persistence.cutover_activation_snapshots import (
    SCHEMA_HEAD,
    capture_snapshot,
    lock_active_administrator,
    require_current_schema,
    require_no_blocking_drift,
)

API_ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.postgres


def _migrate(url: str) -> Engine:
    config = Config(str(API_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "head")
    return create_engine(url)


def _state(engine: Engine, namespace: str, payload: dict[str, object]) -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO coeus_state(namespace,payload,updated_at) "
                "VALUES (:namespace,CAST(:payload AS jsonb),now()) "
                "ON CONFLICT (namespace) DO UPDATE SET payload=EXCLUDED.payload"
            ),
            {"namespace": namespace, "payload": json.dumps(payload)},
        )


def _account(engine: Engine, user_id: UUID, *, active: bool = True, admin: bool = True) -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO identity_account_projection"
                "(user_id,is_active,roles,credential_version,source_hash) "
                "VALUES (:actor,:active,CAST(:roles AS text[]),1,:hash)"
            ),
            {
                "actor": user_id,
                "active": active,
                "roles": ["Administrator"] if admin else ["Analyst"],
                "hash": "a" * 64,
            },
        )


def test_an_empty_database_reports_parity_for_every_slice(postgres_database_url: str) -> None:
    engine = _migrate(postgres_database_url)

    with engine.connect() as connection:
        snapshots = {slice: capture_snapshot(connection, slice) for slice in CutoverSlice}

    for snapshot in snapshots.values():
        assert snapshot.parity
        assert snapshot.source_count == snapshot.target_count == 0
        assert snapshot.source_hash == snapshot.target_hash == snapshot.visibility_hash
    engine.dispose()


def test_a_legacy_record_the_relational_side_lacks_breaks_parity(
    postgres_database_url: str,
) -> None:
    engine = _migrate(postgres_database_url)
    team = OrgTeam(uuid4(), "Synthetic Team", TeamKind.RFA, member_user_ids=(uuid4(),))
    _state(engine, "teams", {"items": [encode_value(team)]})

    with engine.connect() as connection:
        snapshot = capture_snapshot(connection, CutoverSlice.ORGANISATION)

    assert not snapshot.parity
    assert snapshot.source_count == 1 and snapshot.target_count == 0
    assert snapshot.source_hash != snapshot.target_hash
    engine.dispose()


@pytest.mark.parametrize(
    ("namespace", "slice"),
    [("teams", CutoverSlice.ORGANISATION), ("team_calendar", CutoverSlice.CALENDAR)],
)
def test_an_unexpected_legacy_record_type_fails_closed(
    postgres_database_url: str, namespace: str, slice: CutoverSlice
) -> None:
    engine = _migrate(postgres_database_url)
    _state(engine, namespace, {"items": [{"not": "a record"}]})

    with engine.connect() as connection, pytest.raises(ValueError, match="invalid record type"):
        capture_snapshot(connection, slice)
    engine.dispose()


def test_the_schema_head_and_drift_checks_pass_on_a_current_database(
    postgres_database_url: str,
) -> None:
    engine = _migrate(postgres_database_url)

    with engine.connect() as connection:
        require_current_schema(connection)
        require_no_blocking_drift(connection)
        assert (
            connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
            == SCHEMA_HEAD
        )
    engine.dispose()


def test_an_older_schema_head_refuses_the_candidate(postgres_database_url: str) -> None:
    engine = _migrate(postgres_database_url)
    with engine.begin() as connection:
        connection.execute(text("UPDATE alembic_version SET version_num='20260804_0036'"))

    with engine.connect() as connection, pytest.raises(ValueError, match="current schema head"):
        require_current_schema(connection)
    engine.dispose()


def test_only_an_active_administrator_may_hold_the_activation_lock(
    postgres_database_url: str,
) -> None:
    engine = _migrate(postgres_database_url)
    administrator, suspended, analyst = uuid4(), uuid4(), uuid4()
    _account(engine, administrator)
    _account(engine, suspended, active=False)
    _account(engine, analyst, admin=False)

    with engine.begin() as connection:
        lock_active_administrator(connection, administrator)
        for actor in (suspended, analyst, uuid4()):
            with pytest.raises(PermissionError, match="active human administrator"):
                lock_active_administrator(connection, actor)
    engine.dispose()
