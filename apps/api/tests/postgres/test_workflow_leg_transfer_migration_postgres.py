"""Real PostgreSQL concurrency and immutability gates for transfer evidence."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import DBAPIError, IntegrityError

pytestmark = pytest.mark.postgres
API_ROOT = Path(__file__).resolve().parents[2]


def _upgrade(database_url: str) -> None:
    config = Config(str(API_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "20260804_0039")


def test_transfer_schema_is_actor_scoped_and_evidence_is_immutable(
    postgres_database_url: str,
) -> None:
    _upgrade(postgres_database_url)
    engine = create_engine(postgres_database_url)
    actor_a, actor_b, transfer_id = uuid4(), uuid4(), _insert_transfer(engine)
    values = {
        "actor": actor_a,
        "command": uuid4(),
        "key": "same-key",
        "transfer": transfer_id,
    }
    with engine.begin() as connection:
        _insert_command(connection, values)
        _insert_command(connection, {**values, "actor": actor_b, "command": uuid4()})
    with pytest.raises(IntegrityError), engine.begin() as connection:
        _insert_command(connection, {**values, "command": uuid4()})
    with pytest.raises(DBAPIError), engine.begin() as connection:
        connection.execute(
            text("""UPDATE workflow_leg_transfer_commands
SET result_version=99 WHERE command_id=:command"""),
            values,
        )
    with pytest.raises(DBAPIError), engine.begin() as connection:
        connection.execute(
            text("UPDATE workflow_leg_transfers SET reason='changed' WHERE transfer_id=:transfer"),
            values,
        )
    engine.dispose()


def test_downgrade_refuses_to_destroy_transfer_evidence(postgres_database_url: str) -> None:
    _upgrade(postgres_database_url)
    engine = create_engine(postgres_database_url)
    _insert_transfer(engine)
    config = Config(str(API_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", postgres_database_url)
    with pytest.raises(DBAPIError):
        command.downgrade(config, "20260804_0038")
    with engine.begin() as connection:
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == (
            "20260804_0039"
        )
    engine.dispose()


def test_concurrent_same_actor_key_has_exactly_one_winner(postgres_database_url: str) -> None:
    _upgrade(postgres_database_url)
    engine = create_engine(postgres_database_url)
    transfer_id = _insert_transfer(engine)
    actor = uuid4()

    def insert(command_id: object) -> bool:
        try:
            with engine.begin() as connection:
                _insert_command(
                    connection,
                    {
                        "actor": actor,
                        "command": command_id,
                        "key": "concurrent-key",
                        "transfer": transfer_id,
                    },
                )
            return True
        except IntegrityError:
            return False

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = tuple(executor.map(insert, (uuid4(), uuid4())))
    assert sorted(results) == [False, True]
    engine.dispose()


def _insert_transfer(engine: Engine) -> object:
    transfer_id, ticket_id, source, target, user, manager, grant = (uuid4() for _ in range(7))
    with engine.begin() as connection:
        now = connection.execute(text("SELECT transaction_timestamp()")).scalar_one()
        for unit_id, name in ((source, "Source"), (target, "Target")):
            connection.execute(
                text("""INSERT INTO organisation_units
(unit_id,name,short_name,category,is_active,valid_from,time_zone,version)
VALUES(:id,:name,:name,'delivery_team',true,:at,'Europe/London',1)"""),
                {"id": unit_id, "name": name, "at": now},
            )
            connection.execute(
                text("""INSERT INTO organisation_unit_closure
(ancestor_unit_id,descendant_unit_id,depth) VALUES(:id,:id,0)"""),
                {"id": unit_id},
            )
        connection.execute(
            text("""INSERT INTO workflow_leg_transfers
(transfer_id,ticket_id,workflow_leg,source_unit_id,target_unit_id,target_user_id,
source_manager_user_id,state,expected_ownership_version,expected_ticket_version,
expected_ticket_source_hash,source_grant_id,source_grant_version,proposal_hash,preview_hash,
expires_at,reason,version,created_at,updated_at) VALUES
(:id,:ticket,'rfa',:source,:target,:user,:manager,'proposed',1,1,:hash,:grant,1,:hash,:hash,
:expires,'test',1,:at,:at)"""),
            {
                "id": transfer_id,
                "ticket": ticket_id,
                "source": source,
                "target": target,
                "user": user,
                "manager": manager,
                "grant": grant,
                "hash": "a" * 64,
                "expires": now.replace(year=now.year + 1),
                "at": now,
            },
        )
    return transfer_id


def _insert_command(connection: Connection, values: dict[str, object]) -> None:
    connection.execute(
        text("""INSERT INTO workflow_leg_transfer_commands
(command_id,actor_user_id,idempotency_key,transfer_id,action,request_hash,result_state,
result_version,occurred_at) VALUES(:command,:actor,:key,:transfer,'propose',:hash,
'proposed',1,transaction_timestamp())"""),
        {**values, "hash": "b" * 64},
    )
