from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from coeus.core.config import Settings
from coeus.domain.search_index import (
    SearchAssetIndexState,
    SearchChunk,
    SearchChunkEmbedding,
    SearchIndexProfile,
    SearchTicketDocument,
    SearchTicketEmbedding,
)
from coeus.domain.store import StoreVisibilityScope
from coeus.persistence.search_index_repository import (
    MemorySearchIndexRepository,
    _group_rows,
    _vector,
)
from coeus.services.search_composition import build_search_index_repository
from coeus.services.search_configuration import SEARCH_EMBEDDING_DIMENSIONS

VECTOR = (0.0,) * SEARCH_EMBEDDING_DIMENSIONS


def test_memory_index_search_honours_an_explicit_empty_visibility_set() -> None:
    repository = MemorySearchIndexRepository()
    product_id = uuid4()
    chunk = _chunk(product_id, "Synthetic Russian armour movement in Donbas")
    profile = _profile(1, "first", products=1, chunks=1, active=True)
    repository.begin(_profile(1, "first", products=1, chunks=0))
    repository.activate(profile, (chunk,), (_embedding(chunk),))

    scope = StoreVisibilityScope(frozenset({uuid4()}), 3, False)
    assert repository.search(scope, "Russian armour", None, frozenset()) == ()

    results = repository.search(scope, "Russian armour", None, frozenset({product_id}))
    assert len(results) == 1
    assert results[0].product_id == product_id
    assert results[0].passages[0].excerpt.startswith("Synthetic Russian")


def test_failed_shadow_activation_restores_the_previous_ready_profile() -> None:
    repository = MemorySearchIndexRepository()
    first_product = uuid4()
    first_chunk = _chunk(first_product, "first generation evidence")
    first = _profile(1, "first", products=1, chunks=1, active=True)
    repository.begin(_profile(1, "first", products=1, chunks=0))
    repository.activate(first, (first_chunk,), (_embedding(first_chunk),))

    second_product = uuid4()
    second_chunk = _chunk(second_product, "second generation evidence")
    second = _profile(2, "second", products=1, chunks=1, active=True)
    repository.begin(_profile(2, "second", products=1, chunks=0))
    repository.activate(second, (second_chunk,), (_embedding(second_chunk),))
    repository.rollback_activation(second.profile_id, "index_write_failed")

    assert repository.counts() == (1, 1, 0, 0, "first")
    scope = StoreVisibilityScope(frozenset({uuid4()}), 3, False)
    results = repository.search(scope, "first generation", None, frozenset({first_product}))
    assert [result.product_id for result in results] == [first_product]


def test_index_rejects_missing_or_malformed_vectors() -> None:
    repository = MemorySearchIndexRepository()
    chunk = _chunk(uuid4(), "evidence")
    profile = _profile(1, "first", products=1, chunks=1, active=True)
    repository.begin(_profile(1, "first", products=1, chunks=0))
    with pytest.raises(ValueError, match="exactly one"):
        repository.activate(profile, (chunk,), ())

    with pytest.raises(ValueError, match="1,536 finite"):
        repository.activate(
            profile,
            (chunk,),
            (SearchChunkEmbedding(chunk.chunk_id, "source", (0.0,) * 12),),
        )


def test_ticket_search_prefilters_authorised_ids_and_active_states() -> None:
    repository = MemorySearchIndexRepository()
    allowed_id, hidden_id, closed_id = uuid4(), uuid4(), uuid4()
    documents = (
        _ticket_document(allowed_id, "RFI_SEARCHING", "Donbas armour movement"),
        _ticket_document(hidden_id, "RFI_SEARCHING", "Donbas armour movement"),
        _ticket_document(closed_id, "CANCELLED", "Donbas armour movement"),
    )
    profile = _profile(1, "tickets", products=0, chunks=0, active=True)
    repository.begin(_profile(1, "tickets", products=0, chunks=0))
    repository.activate(
        profile,
        (),
        (),
        documents,
        tuple(_ticket_embedding(document, 0) for document in documents),
    )

    hits = repository.search_tickets(
        "Donbas armour",
        _unit_vector(0),
        frozenset({allowed_id, closed_id}),
        frozenset({"RFI_SEARCHING"}),
    )

    assert [hit.ticket_id for hit in hits] == [allowed_id]
    assert hits[0].lexical_rank == 1
    assert hits[0].vector_rank == 1


def test_ticket_index_rejects_incomplete_embeddings() -> None:
    repository = MemorySearchIndexRepository()
    document = _ticket_document(uuid4(), "RFI_SEARCHING", "Synthetic requirement")
    profile = _profile(1, "tickets", products=0, chunks=0, active=True)
    repository.begin(_profile(1, "tickets", products=0, chunks=0))

    with pytest.raises(ValueError, match="search ticket"):
        repository.activate(profile, (), (), (document,), ())


def test_index_counts_include_active_tickets_and_asset_warnings() -> None:
    repository = MemorySearchIndexRepository()
    product_id, asset_id, ticket_id = uuid4(), uuid4(), uuid4()
    document = _ticket_document(ticket_id, "RFI_SEARCHING", "Synthetic requirement")
    profile = _profile(1, "counts", products=1, chunks=0, active=True)
    repository.begin(_profile(1, "counts", products=1, chunks=0))
    repository.activate(
        profile,
        (),
        (),
        (document,),
        (_ticket_embedding(document, 0),),
        (
            SearchAssetIndexState(
                profile.profile_id,
                product_id,
                asset_id,
                "a" * 64,
                "unsupported",
                0,
                0,
                "asset_type_unsupported",
            ),
        ),
    )

    assert repository.counts() == (1, 0, 1, 1, "counts")


def test_index_rejects_overlapping_builds_and_rolls_back_without_previous_profile() -> None:
    repository = MemorySearchIndexRepository()
    building = _profile(1, "building", products=0, chunks=0)
    repository.begin(building)
    with pytest.raises(RuntimeError, match="already running"):
        repository.begin(_profile(2, "overlap", products=0, chunks=0))

    ready = _profile(1, "building", products=0, chunks=0, active=True)
    repository.activate(ready, (), ())
    repository.rollback_activation(ready.profile_id, "index_write_failed")
    assert repository.counts() == (0, 0, 0, 0, "unindexed")


def test_search_ignores_stale_chunks_and_irrelevant_evidence() -> None:
    repository = MemorySearchIndexRepository()
    old_product = uuid4()
    old_chunk = _chunk(old_product, "old unrelated evidence")
    old = _profile(1, "old", products=1, chunks=1, active=True)
    repository.begin(_profile(1, "old", products=1, chunks=0))
    repository.activate(old, (old_chunk,), (_embedding(old_chunk),))

    current = _profile(2, "current", products=0, chunks=0, active=True)
    repository.begin(_profile(2, "current", products=0, chunks=0))
    repository.activate(current, (), ())
    scope = StoreVisibilityScope(frozenset({uuid4()}), 3, False)

    assert repository.search(scope, "missing", None, None) == ()
    assert repository.search_tickets("missing", None, frozenset(), frozenset()) == ()


def test_ticket_search_skips_missing_embeddings_and_below_threshold_scores() -> None:
    repository = MemorySearchIndexRepository()
    ticket_id = uuid4()
    document = _ticket_document(ticket_id, "RFI_SEARCHING", "unrelated requirement")
    profile = _profile(1, "tickets", products=0, chunks=0, active=True)
    repository.begin(_profile(1, "tickets", products=0, chunks=0))
    repository.activate(
        profile,
        (),
        (),
        (document,),
        (_ticket_embedding(document, 0),),
    )
    repository._ticket_embeddings.clear()

    assert (
        repository.search_tickets(
            "missing",
            _unit_vector(1),
            frozenset({ticket_id}),
            frozenset({"RFI_SEARCHING"}),
        )
        == ()
    )


def test_grouping_caps_passages_and_vector_codec_handles_optional_values() -> None:
    product_id = uuid4()
    rows = []
    for index in range(5):
        chunk = _chunk(product_id, f"evidence {index}")
        rows.append(
            {
                **chunk.__dict__,
                "asset_id": None,
                "lexical_score": 1.0,
                "vector_score": 0.0,
                "lexical_rank": index + 1,
                "vector_rank": None,
            }
        )

    evidence = _group_rows(tuple(rows))
    assert len(evidence[0].passages) == 3
    assert evidence[0].lexical_rank == 1
    assert _vector(None) is None
    assert _vector(_unit_vector(0)).startswith("[1.00000000")
    with pytest.raises(ValueError, match="1,536 finite"):
        _vector((float("nan"),) * SEARCH_EMBEDDING_DIMENSIONS)


def test_repository_builder_selects_memory_or_postgres(monkeypatch: pytest.MonkeyPatch) -> None:
    assert isinstance(
        build_search_index_repository(Settings(environment="test", persistence_provider="memory")),
        MemorySearchIndexRepository,
    )

    sentinel = MemorySearchIndexRepository()
    monkeypatch.setattr(
        "coeus.persistence.search_index_postgres.build_postgres_search_index",
        lambda _settings: sentinel,
    )
    assert (
        build_search_index_repository(Settings(environment="test", persistence_provider="postgres"))
        is sentinel
    )


def _profile(
    generation: int,
    corpus: str,
    *,
    products: int,
    chunks: int,
    active: bool = False,
) -> SearchIndexProfile:
    return SearchIndexProfile(
        profile_id=_profile_id(generation, corpus),
        provider="mock",
        model="token-hash-v2",
        dimensions=SEARCH_EMBEDDING_DIMENSIONS,
        generation=generation,
        space_id=f"mock:token-hash-v2:1536:g{generation}",
        status="ready" if active else "indexing",
        is_active=active,
        corpus_version=corpus,
        product_count=products,
        chunk_count=chunks,
        indexed_count=chunks,
        failed_count=0,
        created_by_user_id=uuid4(),
        created_at=datetime.now(UTC),
    )


def _profile_id(generation: int, corpus: str) -> UUID:
    from uuid import NAMESPACE_URL, uuid5

    return uuid5(NAMESPACE_URL, f"{generation}:{corpus}")


def _chunk(product_id: UUID, content: str) -> SearchChunk:
    from hashlib import sha256

    content_hash = sha256(content.encode()).hexdigest()
    return SearchChunk(
        chunk_id=uuid4(),
        product_id=product_id,
        asset_id=None,
        asset_name="Product metadata",
        asset_sha256=None,
        page_number=0,
        chunk_index=0,
        content=content,
        content_hash=content_hash,
        extractor_version="metadata-v1",
        chunker_version="test-v1",
    )


def _embedding(chunk: SearchChunk) -> SearchChunkEmbedding:
    return SearchChunkEmbedding(chunk.chunk_id, "source", VECTOR)


def _ticket_document(ticket_id: UUID, state: str, content: str) -> SearchTicketDocument:
    from hashlib import sha256

    return SearchTicketDocument(ticket_id, state, content, sha256(content.encode()).hexdigest())


def _ticket_embedding(document: SearchTicketDocument, dimension: int) -> SearchTicketEmbedding:
    return SearchTicketEmbedding(document.ticket_id, document.content_hash, _unit_vector(dimension))


def _unit_vector(dimension: int) -> tuple[float, ...]:
    return tuple(1.0 if index == dimension else 0.0 for index in range(1536))
