"""Exercise Alembic against disposable real PostgreSQL databases."""

import json
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from coeus.domain.enums import TicketState
from coeus.domain.tickets import IntakeDetails, TicketRecord
from coeus.persistence.codec import CodecWriteFormat, encode_value
from coeus.persistence.resource_lease_schema import RESOURCE_LEASE_SCHEMA_SQL
from coeus.persistence.state_store import PostgresStateStore
from coeus.persistence.ticket_reverse_projection import reverse_project_ticket_state
from coeus.persistence.ticket_shadow_schema import ensure_ticket_shadow_schema
from coeus.repositories.tickets import InMemoryTicketRepository

API_ROOT = Path(__file__).resolve().parents[2]
HEAD_REVISION = "20260804_0045"

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
            indexes = set(
                connection.execute(
                    text("SELECT indexname FROM pg_indexes WHERE tablename = 'coeus_outbox'")
                ).scalars()
            )
            search_indexes = set(
                connection.execute(
                    text(
                        "SELECT indexname FROM pg_indexes WHERE tablename = 'search_index_profiles'"
                    )
                ).scalars()
            )
            ticket_document_key = inspect(engine).get_pk_constraint("ticket_search_documents")[
                "constrained_columns"
            ]
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
        "search_index_profiles",
        "intelligence_store_search_chunks",
        "intelligence_store_chunk_embeddings",
        "intelligence_store_asset_index_state",
        "ticket_search_documents",
        "ticket_search_embeddings",
        "canonical_work_packages",
        "work_package_participants",
        "work_package_dependencies",
        "capacity_reservations",
        "work_package_history",
        "work_package_commands",
        "work_package_contributor_commands",
        "work_package_dependency_commands",
        "work_package_handover_commands",
        "calendar_import_commands",
        "calendar_legacy_import_records",
        "working_patterns",
        "synthetic_organisation_fixture_commands",
        "assignment_competencies",
        "identity_account_projection",
        "capacity_exceptions",
    } <= tables
    assert "vector" in extensions
    assert "idx_coeus_outbox_dead_letters" in indexes
    assert "idx_search_index_one_building" in search_indexes
    assert ticket_document_key == ["profile_id", "ticket_id"]


def test_search_generation_upgrade_invalidates_profiles_with_cleared_ticket_data(
    postgres_database_url: str,
) -> None:
    config = _alembic(postgres_database_url)
    command.upgrade(config, "20260727_0015")
    profile_id = uuid4()
    ticket_id = uuid4()
    engine = create_engine(postgres_database_url)
    try:
        with engine.begin() as connection:
            connection.execute(text("DROP TABLE ticket_search_embeddings"))
            connection.execute(text("DROP TABLE ticket_search_documents"))
            connection.execute(
                text(
                    "CREATE TABLE ticket_search_documents ("
                    "ticket_id uuid PRIMARY KEY, state text NOT NULL, content text NOT NULL, "
                    "content_hash char(64) NOT NULL, search_document tsvector NOT NULL, "
                    "updated_at timestamptz NOT NULL DEFAULT now())"
                )
            )
            connection.execute(
                text(
                    "CREATE TABLE ticket_search_embeddings ("
                    "profile_id uuid NOT NULL REFERENCES search_index_profiles(profile_id) "
                    "ON DELETE CASCADE, ticket_id uuid NOT NULL REFERENCES "
                    "ticket_search_documents(ticket_id) ON DELETE CASCADE, "
                    "source_hash char(64) NOT NULL, embedding vector(1536) NOT NULL, "
                    "indexed_at timestamptz NOT NULL DEFAULT now(), "
                    "PRIMARY KEY(profile_id, ticket_id))"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO search_index_profiles("
                    "profile_id, provider, model, dimensions, generation, space_id, status, "
                    "is_active, corpus_version, product_count, chunk_count, indexed_count, "
                    "failed_count, created_by_user_id, completed_at) VALUES ("
                    ":profile_id, 'mock', 'token-hash-v2', 1536, 1, 'migration-test', "
                    "'ready', true, 'corpus', 1, 1, 1, 0, :user_id, now())"
                ),
                {"profile_id": profile_id, "user_id": uuid4()},
            )
            connection.execute(
                text(
                    "INSERT INTO ticket_search_documents("
                    "ticket_id, state, content, content_hash, search_document) VALUES ("
                    ":ticket_id, 'RFI_SEARCHING', 'synthetic request', :content_hash, "
                    "to_tsvector('english', 'synthetic request'))"
                ),
                {"ticket_id": ticket_id, "content_hash": "a" * 64},
            )

        command.upgrade(config, "head")
        with engine.connect() as connection:
            profile = connection.execute(
                text(
                    "SELECT status, is_active, error_code FROM search_index_profiles "
                    "WHERE profile_id = :profile_id"
                ),
                {"profile_id": profile_id},
            ).one()
            document_count = connection.execute(
                text("SELECT count(*) FROM ticket_search_documents")
            ).scalar_one()
            ticket_document_key = inspect(engine).get_pk_constraint("ticket_search_documents")[
                "constrained_columns"
            ]
    finally:
        engine.dispose()

    assert tuple(profile) == ("failed", False, "index_write_failed")
    assert document_count == 0
    assert ticket_document_key == ["profile_id", "ticket_id"]


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


def test_runtime_bootstrapped_schema_upgrades_to_head(postgres_database_url: str) -> None:
    """Reconcile databases bootstrapped lazily before Alembic advanced."""
    config = _alembic(postgres_database_url)
    command.upgrade(config, "20260710_0006")
    ticket = TicketRecord(
        ticket_id=uuid4(),
        reference="TCK-RUNTIME-BOOTSTRAP",
        requester_user_id=uuid4(),
        state=TicketState.DRAFT_INTAKE,
        intake=IntakeDetails(title="Synthetic runtime bootstrap"),
    )
    engine = create_engine(postgres_database_url)
    try:
        with engine.begin() as connection:
            connection.execute(text(RESOURCE_LEASE_SCHEMA_SQL))
            ensure_ticket_shadow_schema(connection)
            connection.execute(
                text(
                    "INSERT INTO coeus_state(namespace, payload) "
                    "VALUES ('tickets', CAST(:payload AS jsonb))"
                ),
                {"payload": json.dumps({"tickets": [encode_value(ticket)]})},
            )

        command.upgrade(config, "head")
        with engine.connect() as connection:
            requester_user_id = connection.execute(
                text(
                    "SELECT requester_user_id FROM coeus_ticket_aggregates "
                    "WHERE ticket_id = :ticket_id"
                ),
                {"ticket_id": ticket.ticket_id},
            ).scalar_one()
    finally:
        engine.dispose()

    assert requester_user_id == ticket.requester_user_id
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


def test_legacy_ticket_upgrade_supports_validation_mutation_and_reverse_projection(
    postgres_database_url: str,
) -> None:
    config = _alembic(postgres_database_url)
    command.upgrade(config, "20260713_0007")
    ticket = TicketRecord(
        ticket_id=uuid4(),
        reference="TCK-LEGACY-UPGRADE",
        requester_user_id=uuid4(),
        state=TicketState.DRAFT_INTAKE,
        intake=IntakeDetails(title="Synthetic legacy upgrade"),
    )
    legacy_ticket = encode_value(ticket, write_format=CodecWriteFormat.LEGACY)
    engine = create_engine(postgres_database_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO coeus_state(namespace, payload) "
                "VALUES ('tickets', CAST(:payload AS jsonb))"
            ),
            {"payload": json.dumps({"counter": 1, "tickets": [legacy_ticket]})},
        )

    command.upgrade(config, "head")
    store = PostgresStateStore(postgres_database_url, "relational")
    repository = InMemoryTicketRepository(store)
    assert repository.get(ticket.ticket_id) == ticket
    updated = replace(ticket, state=TicketState.INFO_REQUIRED)
    assert repository.save_if_current(ticket, updated)
    assert reverse_project_ticket_state(postgres_database_url) == 1

    with engine.connect() as connection:
        payload = connection.execute(
            text("SELECT payload FROM coeus_state WHERE namespace = 'tickets'")
        ).scalar_one()
    restored = payload["tickets"][0]
    assert restored["fields"]["state"]["value"] == TicketState.INFO_REQUIRED.value
