"""Migration coverage for handover and reservation identity changes."""

from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import DBAPIError

API_ROOT = Path(__file__).resolve().parents[2]

pytestmark = pytest.mark.postgres


def _alembic(database_url: str) -> Config:
    config = Config(str(API_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def _reservation_unique_columns(engine: Engine) -> set[tuple[str, ...]]:
    return {
        tuple(item["column_names"])
        for item in inspect(engine).get_unique_constraints("capacity_reservations")
    }


def test_handover_upgrade_scopes_capacity_keys_and_round_trips(
    postgres_database_url: str,
) -> None:
    config = _alembic(postgres_database_url)
    command.upgrade(config, "20260804_0035")
    engine = create_engine(postgres_database_url)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "ALTER TABLE capacity_reservations DROP CONSTRAINT "
                    "uq_capacity_reservation_actor_key"
                )
            )
            connection.execute(
                text(
                    "ALTER TABLE capacity_reservations ADD CONSTRAINT "
                    "capacity_reservations_idempotency_key_key UNIQUE(idempotency_key)"
                )
            )
        command.upgrade(config, "20260804_0036")
        composite = _reservation_unique_columns(engine)
        assert ("actor_user_id", "idempotency_key") in composite
        assert ("idempotency_key",) not in composite

        command.downgrade(config, "20260804_0035")
        assert ("idempotency_key",) in _reservation_unique_columns(engine)

        command.upgrade(config, "20260804_0036")
        assert ("actor_user_id", "idempotency_key") in _reservation_unique_columns(engine)
    finally:
        engine.dispose()


def test_handover_downgrade_refuses_cross_actor_key_evidence_atomically(
    postgres_database_url: str,
) -> None:
    config = _alembic(postgres_database_url)
    command.upgrade(config, "20260804_0036")
    engine = create_engine(postgres_database_url)
    package_id, ticket_id, unit_id, owner_id = uuid4(), uuid4(), uuid4(), uuid4()
    actor_one, actor_two = uuid4(), uuid4()
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO organisation_units("
                    "unit_id,name,short_name,category,is_active,valid_from,time_zone,description,"
                    "provenance,version) VALUES (:unit,'Migration Team','MIG','command',true,"
                    "transaction_timestamp(),'Europe/London','','migration-test',1)"
                ),
                {"unit": unit_id},
            )
            connection.execute(
                text(
                    "INSERT INTO organisation_unit_closure"
                    "(ancestor_unit_id,descendant_unit_id,depth) VALUES (:unit,:unit,0)"
                ),
                {"unit": unit_id},
            )
            connection.execute(
                text(
                    "INSERT INTO canonical_work_packages("
                    "package_id,ticket_id,workflow_leg,owning_unit_id,accountable_user_id,"
                    "title,state,sort_order,version,provenance,created_at,updated_at) VALUES ("
                    ":package,:ticket,'rfa',:unit,:owner,'Migration evidence','ready',0,1,"
                    "'migration-test',transaction_timestamp(),transaction_timestamp())"
                ),
                {
                    "package": package_id,
                    "ticket": ticket_id,
                    "unit": unit_id,
                    "owner": owner_id,
                },
            )
            connection.execute(
                text(
                    "INSERT INTO capacity_reservations("
                    "reservation_id,user_id,ticket_id,workflow_leg,package_id,starts_at,ends_at,"
                    "reserved_minutes,state,idempotency_key,request_hash,actor_user_id,version,"
                    "created_at,updated_at) VALUES "
                    "(:first,:owner,:ticket,'rfa',:package,transaction_timestamp(),"
                    "transaction_timestamp()+interval '1 hour',60,'active','shared-key',:hash_one,"
                    ":actor_one,1,transaction_timestamp(),transaction_timestamp()),"
                    "(:second,:owner,:ticket,'rfa',:package,transaction_timestamp(),"
                    "transaction_timestamp()+interval '1 hour',60,'active','shared-key',:hash_two,"
                    ":actor_two,1,transaction_timestamp(),transaction_timestamp())"
                ),
                {
                    "first": uuid4(),
                    "second": uuid4(),
                    "owner": owner_id,
                    "ticket": ticket_id,
                    "package": package_id,
                    "hash_one": "a" * 64,
                    "hash_two": "b" * 64,
                    "actor_one": actor_one,
                    "actor_two": actor_two,
                },
            )

        with pytest.raises(DBAPIError, match="cannot represent actor-scoped capacity keys"):
            command.downgrade(config, "20260804_0035")

        with engine.connect() as connection:
            revision = connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one()
            rows = connection.execute(
                text(
                    "SELECT count(*) FROM capacity_reservations WHERE idempotency_key='shared-key'"
                )
            ).scalar_one()
            handover_table = connection.execute(
                text("SELECT to_regclass('work_package_handover_commands')")
            ).scalar_one()
        assert revision == "20260804_0036"
        assert rows == 2 and handover_table == "work_package_handover_commands"
        assert ("actor_user_id", "idempotency_key") in _reservation_unique_columns(engine)
    finally:
        engine.dispose()
