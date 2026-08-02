from datetime import UTC, datetime
from hashlib import sha256
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

import pytest

from coeus.domain.search_index import (
    SEARCH_EMBEDDING_DIMENSIONS,
    SearchIndexProfile,
    SearchTicketDocument,
    SearchTicketEmbedding,
)
from coeus.persistence.search_index_repository import MemorySearchIndexRepository
from coeus.persistence.search_index_validation import embedding_source_hash


def test_interrupted_memory_build_is_recovered_and_can_retry() -> None:
    repository = MemorySearchIndexRepository()
    repository.begin(_profile(1, "interrupted"))

    assert repository.recover_interrupted() == 1
    repository.begin(_profile(2, "retry"))
    assert repository.recover_interrupted() == 1
    assert repository.recover_interrupted() == 0


def test_activation_requires_a_live_candidate_and_preserves_previous_profile() -> None:
    repository = MemorySearchIndexRepository()
    repository.begin(_profile(1, "first"))
    repository.activate(_profile(1, "first", active=True), (), ())

    with pytest.raises(RuntimeError, match="not indexing"):
        repository.activate(_profile(2, "stale", active=True), (), ())

    assert repository.counts() == (0, 0, 0, 0, "first")


def test_ticket_documents_remain_scoped_to_their_generation_after_rollback() -> None:
    repository = MemorySearchIndexRepository()
    ticket_id = uuid4()
    first_document = _document(ticket_id, "first generation phrase")
    first_build = _profile(1, "first")
    first_ready = _profile(1, "first", active=True)
    repository.begin(first_build)
    repository.activate(
        first_ready,
        (),
        (),
        (first_document,),
        (_embedding(first_document, 0, first_ready),),
    )
    second_document = _document(ticket_id, "second generation phrase")
    second = _profile(2, "second", active=True)
    repository.begin(_profile(2, "second"))
    repository.activate(
        second,
        (),
        (),
        (second_document,),
        (_embedding(second_document, 1, second),),
    )
    repository.rollback_activation(second.profile_id, "index_write_failed")

    hits = repository.search_tickets(
        "first generation phrase",
        _unit_vector(0),
        frozenset({ticket_id}),
        frozenset({"RFI_SEARCHING"}),
    )

    assert [hit.ticket_id for hit in hits] == [ticket_id]
    assert hits[0].lexical_rank == 1


def _profile(generation: int, corpus: str, *, active: bool = False) -> SearchIndexProfile:
    return SearchIndexProfile(
        profile_id=uuid5(NAMESPACE_URL, f"{generation}:{corpus}"),
        provider="mock",
        model="token-hash-v2",
        dimensions=SEARCH_EMBEDDING_DIMENSIONS,
        generation=generation,
        space_id=f"mock:token-hash-v2:1536:g{generation}",
        status="ready" if active else "indexing",
        is_active=active,
        corpus_version=corpus,
        product_count=0,
        chunk_count=0,
        indexed_count=0,
        failed_count=0,
        created_by_user_id=uuid4(),
        created_at=datetime.now(UTC),
    )


def _document(ticket_id: UUID, content: str) -> SearchTicketDocument:
    return SearchTicketDocument(
        ticket_id, "RFI_SEARCHING", content, sha256(content.encode()).hexdigest()
    )


def _embedding(
    document: SearchTicketDocument,
    dimension: int,
    profile: SearchIndexProfile,
) -> SearchTicketEmbedding:
    return SearchTicketEmbedding(
        document.ticket_id,
        embedding_source_hash(profile.space_id, document.content_hash),
        _unit_vector(dimension),
    )


def _unit_vector(dimension: int) -> tuple[float, ...]:
    return tuple(1.0 if index == dimension else 0.0 for index in range(SEARCH_EMBEDDING_DIMENSIONS))
