from dataclasses import replace
from datetime import UTC, datetime
from typing import Any, cast
from uuid import uuid4

import pytest
from sqlalchemy.engine import Connection

from coeus.domain.search_index import (
    SEARCH_EMBEDDING_DIMENSIONS,
    SearchAssetIndexState,
    SearchChunk,
    SearchChunkEmbedding,
    SearchIndexProfile,
    SearchTicketDocument,
    SearchTicketEmbedding,
)
from coeus.persistence.search_index_postgres_write import validate_generation, write_generation
from coeus.persistence.search_index_validation import embedding_source_hash

VECTOR = (0.0,) * SEARCH_EMBEDDING_DIMENSIONS


def test_generation_writer_persists_and_atomically_promotes_every_record() -> None:
    connection = _Connection()
    profile = _profile()
    chunk = _chunk()
    document = _document()
    chunk_embedding = SearchChunkEmbedding(
        chunk.chunk_id,
        embedding_source_hash(profile.space_id, chunk.content_hash),
        VECTOR,
    )
    ticket_embedding = SearchTicketEmbedding(
        document.ticket_id,
        embedding_source_hash(profile.space_id, document.content_hash),
        VECTOR,
    )
    state = SearchAssetIndexState(
        profile.profile_id,
        chunk.product_id,
        uuid4(),
        "a" * 64,
        "unsupported",
        0,
        0,
        "asset_type_unsupported",
    )

    validate_generation(
        profile,
        (chunk,),
        (chunk_embedding,),
        (document,),
        (ticket_embedding,),
    )
    write_generation(
        cast(Connection, connection),
        replace(profile, status="ready", is_active=True),
        (chunk,),
        (chunk_embedding,),
        (document,),
        (ticket_embedding,),
        (state,),
    )

    statements = "\n".join(connection.statements)
    assert "INSERT INTO intelligence_store_search_chunks" in statements
    assert "INSERT INTO ticket_search_documents" in statements
    assert "INSERT INTO intelligence_store_asset_index_state" in statements
    assert "SET is_active = false" in statements
    assert "SET is_active = true" in statements


def test_generation_writer_rejects_incomplete_vectors_and_stale_promotions() -> None:
    profile = _profile()
    chunk = _chunk()
    document = _document()
    with pytest.raises(ValueError, match="search chunk"):
        validate_generation(profile, (chunk,), (), (), ())
    with pytest.raises(ValueError, match="search ticket"):
        validate_generation(profile, (), (), (document,), ())
    with pytest.raises(ValueError, match="1,536 finite"):
        validate_generation(
            profile,
            (chunk,),
            (
                SearchChunkEmbedding(
                    chunk.chunk_id,
                    embedding_source_hash(profile.space_id, chunk.content_hash),
                    (0.0,) * 2,
                ),
            ),
            (),
            (),
        )
    with pytest.raises(ValueError, match="1,536 finite"):
        validate_generation(
            profile,
            (),
            (),
            (document,),
            (
                SearchTicketEmbedding(
                    document.ticket_id,
                    embedding_source_hash(profile.space_id, document.content_hash),
                    (0.0,) * 2,
                ),
            ),
        )

    with pytest.raises(RuntimeError, match="not indexing"):
        write_generation(
            cast(Connection, _Connection(complete=False)), _profile(), (), (), (), (), ()
        )
    with pytest.raises(RuntimeError, match="could not be activated"):
        write_generation(
            cast(Connection, _Connection(activate=False)), _profile(), (), (), (), (), ()
        )


def test_generation_writer_rejects_duplicate_mismatched_or_stale_identities() -> None:
    profile = _profile()
    chunk = _chunk()
    chunk_embedding = SearchChunkEmbedding(
        chunk.chunk_id,
        embedding_source_hash(profile.space_id, chunk.content_hash),
        VECTOR,
    )
    document = _document()
    ticket_embedding = SearchTicketEmbedding(
        document.ticket_id,
        embedding_source_hash(profile.space_id, document.content_hash),
        VECTOR,
    )

    with pytest.raises(ValueError, match="chunk identities"):
        validate_generation(profile, (chunk, chunk), (chunk_embedding, chunk_embedding), (), ())
    with pytest.raises(ValueError, match="matching embedding"):
        validate_generation(
            profile,
            (chunk,),
            (replace(chunk_embedding, chunk_id=uuid4()),),
            (),
            (),
        )
    with pytest.raises(ValueError, match="source content"):
        validate_generation(
            profile,
            (chunk,),
            (replace(chunk_embedding, source_hash="f" * 64),),
            (),
            (),
        )
    with pytest.raises(ValueError, match="ticket identities"):
        validate_generation(
            profile, (), (), (document, document), (ticket_embedding, ticket_embedding)
        )
    with pytest.raises(ValueError, match="matching embedding"):
        validate_generation(
            profile,
            (),
            (),
            (document,),
            (replace(ticket_embedding, ticket_id=uuid4()),),
        )
    with pytest.raises(ValueError, match="source content"):
        validate_generation(
            profile,
            (),
            (),
            (document,),
            (replace(ticket_embedding, source_hash="e" * 64),),
        )


class _Result:
    def __init__(self, value: bool = True) -> None:
        self._value = value

    def first(self) -> tuple[str] | None:
        return ("profile",) if self._value else None


class _Connection:
    def __init__(self, *, complete: bool = True, activate: bool = True) -> None:
        self.complete = complete
        self.activate = activate
        self.statements: list[str] = []

    def execute(self, statement: Any, _params: object = None) -> _Result:
        sql = str(statement)
        self.statements.append(sql)
        if "status = 'ready'" in sql and "is_active = false" in sql:
            return _Result(self.complete)
        if "SET is_active = true" in sql:
            return _Result(self.activate)
        return _Result()


def _profile() -> SearchIndexProfile:
    return SearchIndexProfile(
        uuid4(),
        "mock",
        "token-hash-v2",
        SEARCH_EMBEDDING_DIMENSIONS,
        1,
        "mock:token-hash-v2:1536:g1",
        "indexing",
        False,
        "corpus",
        1,
        1,
        1,
        0,
        uuid4(),
        datetime.now(UTC),
    )


def _chunk() -> SearchChunk:
    return SearchChunk(
        uuid4(),
        uuid4(),
        None,
        "Product metadata",
        None,
        0,
        0,
        "synthetic evidence",
        "a" * 64,
        "metadata-v1",
        "test-v1",
    )


def _document() -> SearchTicketDocument:
    return SearchTicketDocument(uuid4(), "RFI_SEARCHING", "synthetic request", "b" * 64)
