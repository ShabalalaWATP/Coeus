from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import replace
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from alembic import command
from alembic.config import Config
from psycopg import sql
from sqlalchemy.engine import make_url

from coeus.domain.enums import TicketState
from coeus.domain.tickets import IntakeDetails, TicketRecord
from coeus.persistence.state_store import PostgresStateStore
from coeus.repositories.tickets import InMemoryTicketRepository
from coeus.services.coordinated_restore import (
    create_backup_bundle,
    restore_backup_bundle,
)
from coeus.services.object_storage import LocalObjectStorage
from store_projection_helpers import seed_product

pytestmark = pytest.mark.postgres


def test_coordinated_restore_recovers_database_and_exact_object_bytes(
    postgres_database_url: str, tmp_path: Path
) -> None:
    with _second_database(postgres_database_url) as target_url:
        _upgrade(postgres_database_url)
        store = PostgresStateStore(postgres_database_url, "relational")
        repository = InMemoryTicketRepository(store)
        ticket = TicketRecord(
            ticket_id=uuid4(),
            reference=repository.next_reference(),
            requester_user_id=uuid4(),
            state=TicketState.DRAFT_INTAKE,
            intake=IntakeDetails(title="Restore drill"),
        )
        repository.save(ticket)
        content = b"synthetic coordinated restore evidence\n"
        product = seed_product()
        asset = replace(
            product.assets[0],
            object_key="restore/evidence.bin",
            size_bytes=len(content),
            sha256=sha256(content).hexdigest(),
        )
        product = replace(product, assets=(asset,))
        store.store_projection().save_product(product)
        source_objects = tmp_path / "source-objects"
        LocalObjectStorage(source_objects).write_bytes(asset.object_key, content)
        bundle = tmp_path / "bundle"

        manifest = create_backup_bundle(
            postgres_database_url,
            source_objects,
            bundle,
            confirm_quiesced=True,
        )
        source_objects.joinpath("restore", "evidence.bin").write_bytes(b"corrupted")

        report = restore_backup_bundle(
            postgres_database_url,
            target_url,
            bundle,
            tmp_path / "target-objects",
            confirm_quiesced=True,
        )

        assert report.recovery_id == manifest.recovery_id
        restored = InMemoryTicketRepository(PostgresStateStore(target_url, "relational"))
        assert restored.get(ticket.ticket_id) == ticket
        restored_bytes = LocalObjectStorage(tmp_path / "target-objects").read_bytes(
            asset.object_key
        )
        assert restored_bytes == content


def test_restore_rejects_tampered_bundle_before_target_migration(
    postgres_database_url: str, tmp_path: Path
) -> None:
    with _second_database(postgres_database_url) as target_url:
        _upgrade(postgres_database_url)
        PostgresStateStore(postgres_database_url, "relational").store_projection()
        bundle = tmp_path / "bundle"
        create_backup_bundle(
            postgres_database_url,
            tmp_path / "empty-objects",
            bundle,
            confirm_quiesced=True,
        )
        next(bundle.joinpath("tables").iterdir()).write_bytes(b"tampered")

        with pytest.raises(ValueError, match="failed verification"):
            restore_backup_bundle(
                postgres_database_url,
                target_url,
                bundle,
                tmp_path / "target-objects",
                confirm_quiesced=True,
            )
        with psycopg.connect(_dsn(target_url)) as connection:
            assert connection.execute("SELECT to_regclass('alembic_version')").fetchone()[0] is None


@contextmanager
def _second_database(database_url: str) -> Iterator[str]:
    base = make_url(database_url)
    name = f"coeus_restore_{uuid4().hex}"
    admin_url = base.set(drivername="postgresql", database="postgres")
    with psycopg.connect(admin_url.render_as_string(hide_password=False), autocommit=True) as conn:
        conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    target = base.set(database=name).render_as_string(hide_password=False)
    try:
        yield target
    finally:
        with psycopg.connect(
            admin_url.render_as_string(hide_password=False), autocommit=True
        ) as conn:
            conn.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname=%s AND pid<>pg_backend_pid()",
                (name,),
            )
            conn.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


def _upgrade(database_url: str) -> None:
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "head")


def _dsn(database_url: str) -> str:
    return make_url(database_url).set(drivername="postgresql").render_as_string(hide_password=False)
