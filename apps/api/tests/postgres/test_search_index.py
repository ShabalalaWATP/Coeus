from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine

from coeus.domain.search_index import (
    SearchIndexProfile,
    SearchTicketDocument,
    SearchTicketEmbedding,
)
from coeus.persistence.search_index_postgres import PostgresSearchIndexRepository
from coeus.services.search_configuration import SEARCH_EMBEDDING_DIMENSIONS

API_ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.postgres


def test_postgres_ticket_hybrid_search_prefilters_authorised_ids_and_state(
    postgres_database_url: str,
) -> None:
    config = Config(str(API_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", postgres_database_url)
    command.upgrade(config, "head")
    engine = create_engine(postgres_database_url)
    repository = PostgresSearchIndexRepository(engine)
    profile = _profile()
    allowed = _document("RFI_SEARCHING", "Donbas Russian armour movement")
    hidden = _document("RFI_SEARCHING", "Donbas Russian armour movement")
    closed = _document("CANCELLED", "Donbas Russian armour movement")
    documents = (allowed, hidden, closed)
    try:
        repository.begin(profile)
        repository.activate(
            replace(
                profile,
                status="ready",
                is_active=True,
                completed_at=datetime.now(UTC),
            ),
            (),
            (),
            documents,
            tuple(
                SearchTicketEmbedding(item.ticket_id, item.content_hash, _unit_vector())
                for item in documents
            ),
        )

        hits = repository.search_tickets(
            "Donbas armour",
            _unit_vector(),
            frozenset({allowed.ticket_id, closed.ticket_id}),
            frozenset({"RFI_SEARCHING"}),
        )

        assert [hit.ticket_id for hit in hits] == [allowed.ticket_id]
        assert hits[0].lexical_rank == 1
        assert hits[0].vector_rank == 1
        assert repository.counts() == (0, 0, 3, 0, "postgres-search-test")
    finally:
        engine.dispose()


def _profile() -> SearchIndexProfile:
    return SearchIndexProfile(
        profile_id=uuid4(),
        provider="mock",
        model="token-hash-v2",
        dimensions=SEARCH_EMBEDDING_DIMENSIONS,
        generation=1,
        space_id=f"mock:token-hash-v2:1536:{uuid4()}",
        status="indexing",
        is_active=False,
        corpus_version="postgres-search-test",
        product_count=0,
        chunk_count=0,
        indexed_count=0,
        failed_count=0,
        created_by_user_id=uuid4(),
        created_at=datetime.now(UTC),
    )


def _document(state: str, content: str) -> SearchTicketDocument:
    from hashlib import sha256

    return SearchTicketDocument(uuid4(), state, content, sha256(content.encode()).hexdigest())


def _unit_vector() -> tuple[float, ...]:
    return (1.0, *((0.0,) * (SEARCH_EMBEDDING_DIMENSIONS - 1)))
