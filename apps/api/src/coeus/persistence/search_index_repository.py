"""Generation-aware persistence and access-filtered retrieval for grounded search."""

from collections import defaultdict
from dataclasses import replace
from math import isfinite
from typing import Any, Protocol, cast
from uuid import UUID

from coeus.domain.search_index import (
    SEARCH_EMBEDDING_DIMENSIONS,
    GroundedProductEvidence,
    SearchAssetIndexState,
    SearchChunk,
    SearchChunkEmbedding,
    SearchIndexProfile,
    SearchPassage,
    SearchTicketDocument,
    SearchTicketEmbedding,
    SearchTicketHit,
)
from coeus.domain.store import StoreVisibilityScope

SEARCH_LEG_LIMIT = 100
SEARCH_PASSAGE_LIMIT = 3


class SearchIndexRepository(Protocol):
    def begin(self, profile: SearchIndexProfile) -> None:
        pass

    def activate(
        self,
        profile: SearchIndexProfile,
        chunks: tuple[SearchChunk, ...],
        embeddings: tuple[SearchChunkEmbedding, ...],
        ticket_documents: tuple[SearchTicketDocument, ...] = (),
        ticket_embeddings: tuple[SearchTicketEmbedding, ...] = (),
        asset_states: tuple[SearchAssetIndexState, ...] = (),
    ) -> None:
        pass

    def fail(self, profile_id: UUID, error_code: str) -> None:
        pass

    def rollback_activation(self, profile_id: UUID, error_code: str) -> None:
        pass

    def counts(self) -> tuple[int, int, int, int, str]:
        pass

    def search_tickets(
        self,
        query: str,
        query_vector: tuple[float, ...] | None,
        allowed_ticket_ids: frozenset[UUID],
        states: frozenset[str],
    ) -> tuple[SearchTicketHit, ...]:
        pass

    def search(
        self,
        scope: StoreVisibilityScope,
        query: str,
        query_vector: tuple[float, ...] | None,
        allowed_product_ids: frozenset[UUID] | None = None,
    ) -> tuple[GroundedProductEvidence, ...]:
        pass


class MemorySearchIndexRepository:
    def __init__(self) -> None:
        self._profiles: dict[UUID, SearchIndexProfile] = {}
        self._chunks: dict[UUID, SearchChunk] = {}
        self._embeddings: dict[tuple[UUID, UUID], SearchChunkEmbedding] = {}
        self._ticket_documents: dict[UUID, SearchTicketDocument] = {}
        self._ticket_embeddings: dict[tuple[UUID, UUID], SearchTicketEmbedding] = {}
        self._asset_states: dict[tuple[UUID, UUID], SearchAssetIndexState] = {}
        self._active_id: UUID | None = None
        self._previous_active: dict[UUID, UUID | None] = {}

    def begin(self, profile: SearchIndexProfile) -> None:
        if any(item.status == "indexing" for item in self._profiles.values()):
            raise RuntimeError("search index is already running")
        self._profiles[profile.profile_id] = profile

    def activate(
        self,
        profile: SearchIndexProfile,
        chunks: tuple[SearchChunk, ...],
        embeddings: tuple[SearchChunkEmbedding, ...],
        ticket_documents: tuple[SearchTicketDocument, ...] = (),
        ticket_embeddings: tuple[SearchTicketEmbedding, ...] = (),
        asset_states: tuple[SearchAssetIndexState, ...] = (),
    ) -> None:
        if len(chunks) != len(embeddings):
            raise ValueError("Every search chunk must have exactly one embedding.")
        for chunk_embedding in embeddings:
            _validate_vector(chunk_embedding.vector)
        if len(ticket_documents) != len(ticket_embeddings):
            raise ValueError("Every search ticket must have exactly one embedding.")
        for ticket_embedding in ticket_embeddings:
            _validate_vector(ticket_embedding.vector)
        previous = self._active_id
        if previous is not None:
            self._profiles[previous] = replace(self._profiles[previous], is_active=False)
        self._chunks.update({chunk.chunk_id: chunk for chunk in chunks})
        self._embeddings.update(
            {
                (profile.profile_id, chunk_embedding.chunk_id): chunk_embedding
                for chunk_embedding in embeddings
            }
        )
        self._ticket_documents.update(
            {document.ticket_id: document for document in ticket_documents}
        )
        self._ticket_embeddings.update(
            {
                (profile.profile_id, ticket_embedding.ticket_id): ticket_embedding
                for ticket_embedding in ticket_embeddings
            }
        )
        self._asset_states.update(
            {(state.profile_id, state.asset_id): state for state in asset_states}
        )
        self._profiles[profile.profile_id] = profile
        self._previous_active[profile.profile_id] = previous
        self._active_id = profile.profile_id

    def fail(self, profile_id: UUID, error_code: str) -> None:
        profile = self._profiles[profile_id]
        self._profiles[profile_id] = replace(
            profile,
            status="failed",
            is_active=False,
            error_code=error_code,
        )

    def rollback_activation(self, profile_id: UUID, error_code: str) -> None:
        previous = self._previous_active.pop(profile_id, None)
        self.fail(profile_id, error_code)
        self._active_id = previous
        if previous is not None:
            self._profiles[previous] = replace(self._profiles[previous], is_active=True)

    def counts(self) -> tuple[int, int, int, int, str]:
        if self._active_id is None:
            return 0, 0, 0, 0, "unindexed"
        profile = self._profiles[self._active_id]
        ticket_count = sum(
            profile_id == self._active_id for profile_id, _ in self._ticket_embeddings
        )
        failed_count = sum(
            profile_id == self._active_id and state.status != "indexed"
            for (profile_id, _), state in self._asset_states.items()
        )
        return (
            profile.product_count,
            profile.chunk_count,
            ticket_count,
            failed_count,
            profile.corpus_version,
        )

    def search(
        self,
        scope: StoreVisibilityScope,
        query: str,
        query_vector: tuple[float, ...] | None,
        allowed_product_ids: frozenset[UUID] | None = None,
    ) -> tuple[GroundedProductEvidence, ...]:
        del scope
        if self._active_id is None:
            return ()
        rows: list[dict[str, Any]] = []
        query_tokens = frozenset(query.casefold().split())
        for chunk in self._chunks.values():
            if allowed_product_ids is not None and chunk.product_id not in allowed_product_ids:
                continue
            item = self._embeddings.get((self._active_id, chunk.chunk_id))
            if item is None:
                continue
            lexical = len(query_tokens & frozenset(chunk.content.casefold().split()))
            vector = _cosine(query_vector, item.vector if item else None)
            if lexical or vector >= 0.2:
                rows.append(_memory_row(chunk, float(lexical), vector))
        rows.sort(key=lambda row: (-row["lexical_score"], -row["vector_score"]))
        return _group_rows(tuple(rows[: SEARCH_LEG_LIMIT * 2]))

    def search_tickets(
        self,
        query: str,
        query_vector: tuple[float, ...] | None,
        allowed_ticket_ids: frozenset[UUID],
        states: frozenset[str],
    ) -> tuple[SearchTicketHit, ...]:
        if self._active_id is None or not allowed_ticket_ids:
            return ()
        query_tokens = frozenset(query.casefold().split())
        scored: list[tuple[SearchTicketDocument, float, float]] = []
        for ticket_id in allowed_ticket_ids:
            document = self._ticket_documents.get(ticket_id)
            embedding = self._ticket_embeddings.get((self._active_id, ticket_id))
            if document is None or embedding is None or document.state not in states:
                continue
            lexical = float(len(query_tokens & frozenset(document.content.casefold().split())))
            vector = _cosine(query_vector, embedding.vector)
            scored.append((document, lexical, vector))
        lexical_ranks = _ticket_rank(scored, 1, minimum=0.000001)
        semantic_ranks = _ticket_rank(scored, 2, minimum=0.2)
        selected = set(lexical_ranks) | set(semantic_ranks)
        hits = tuple(
            SearchTicketHit(
                ticket_id,
                lexical_ranks.get(ticket_id, (None, 0.0))[0],
                semantic_ranks.get(ticket_id, (None, 0.0))[0],
                lexical_ranks.get(ticket_id, (None, 0.0))[1],
                semantic_ranks.get(ticket_id, (None, 0.0))[1],
            )
            for ticket_id in selected
        )
        return tuple(sorted(hits, key=_ticket_hit_order))


def _group_rows(rows: tuple[dict[str, Any], ...]) -> tuple[GroundedProductEvidence, ...]:
    grouped: dict[UUID, list[SearchPassage]] = defaultdict(list)
    signals: dict[UUID, tuple[int | None, int | None, float, float]] = {}
    for row in rows:
        product_id = UUID(str(row["product_id"]))
        passage = SearchPassage(
            product_id=product_id,
            chunk_id=UUID(str(row["chunk_id"])),
            asset_id=UUID(str(row["asset_id"])) if row.get("asset_id") else None,
            asset_name=str(row["asset_name"]),
            page_number=int(row["page_number"]),
            excerpt=str(row["content"])[:900],
            lexical_score=float(row.get("lexical_score") or 0),
            vector_score=float(row.get("vector_score") or 0),
            lexical_rank=_optional_int(row.get("lexical_rank")),
            vector_rank=_optional_int(row.get("vector_rank")),
        )
        if len(grouped[product_id]) < SEARCH_PASSAGE_LIMIT:
            grouped[product_id].append(passage)
        current = signals.get(product_id, (None, None, 0.0, 0.0))
        signals[product_id] = (
            _min_rank(current[0], passage.lexical_rank),
            _min_rank(current[1], passage.vector_rank),
            max(current[2], passage.lexical_score),
            max(current[3], passage.vector_score),
        )
    evidence = [
        GroundedProductEvidence(product_id, tuple(passages), *signals[product_id])
        for product_id, passages in grouped.items()
    ]
    return tuple(
        sorted(
            evidence,
            key=lambda item: (-max(item.lexical_score, item.vector_score), str(item.product_id)),
        )
    )


def _vector(value: tuple[float, ...] | None) -> str | None:
    if value is None:
        return None
    _validate_vector(value)
    return "[" + ",".join(f"{item:.8f}" for item in value) + "]"


def _validate_vector(value: tuple[float, ...]) -> None:
    if len(value) != SEARCH_EMBEDDING_DIMENSIONS or any(not isfinite(item) for item in value):
        raise ValueError("Search vectors must contain 1,536 finite dimensions.")


def _optional_int(value: object) -> int | None:
    return None if value is None else int(str(value))


def _min_rank(left: int | None, right: int | None) -> int | None:
    values = [value for value in (left, right) if value is not None]
    return min(values) if values else None


def _cosine(left: tuple[float, ...] | None, right: tuple[float, ...] | None) -> float:
    if left is None or right is None:
        return 0.0
    return max(0.0, sum(a * b for a, b in zip(left, right, strict=True)))


def _memory_row(chunk: SearchChunk, lexical: float, vector: float) -> dict[str, Any]:
    return {
        **chunk.__dict__,
        "lexical_score": lexical,
        "vector_score": vector,
        "lexical_rank": None,
        "vector_rank": None,
    }


def _ticket_rank(
    scored: list[tuple[SearchTicketDocument, float, float]],
    score_index: int,
    *,
    minimum: float,
) -> dict[UUID, tuple[int, float]]:
    def score(item: tuple[SearchTicketDocument, float, float]) -> float:
        return cast(float, item[score_index])

    ranked = sorted(
        (item for item in scored if score(item) >= minimum),
        key=lambda item: (-score(item), str(item[0].ticket_id)),
    )[:SEARCH_LEG_LIMIT]
    return {item[0].ticket_id: (rank, score(item)) for rank, item in enumerate(ranked, start=1)}


def _ticket_hit_order(hit: SearchTicketHit) -> tuple[float, str]:
    rrf = sum(1 / (60 + rank) for rank in (hit.lexical_rank, hit.vector_rank) if rank is not None)
    return -rrf, str(hit.ticket_id)
