from collections.abc import Callable
from uuid import UUID

from coeus.domain.store import StoreHybridCandidate, StoreProduct
from coeus.services.embeddings import EmbeddingService, MockEmbeddingProvider, cosine_similarity
from coeus.services.rfi_ranking import lexical_score_for_product
from coeus.services.store_semantics import product_semantic_text


def memory_hybrid_candidates(
    products: tuple[StoreProduct, ...],
    query: str,
    query_embedding: tuple[float, ...] | None,
    embeddings: EmbeddingService | None = None,
) -> tuple[StoreHybridCandidate, ...]:
    """Return deterministic hybrid candidates when no PostgreSQL projection exists.

    Product vectors come from the same provider as the query vector when an
    ``EmbeddingService`` is supplied, so the cosine comparison stays inside one
    embedding space. Without a service the deterministic mock provider is used,
    which matches the default local configuration where the query vector is also
    a mock vector. Callers should pass the configured service under a non-mock
    provider to avoid comparing vectors from two different embedding spaces.
    """

    lexical_ranked = _rank_lexical(products, query)
    vector_ranked = _rank_vector(products, query_embedding, embeddings)
    # A run is effectively lexical-only when the query never embedded or when no
    # candidate produced a usable vector, so the semantic leg contributed nothing.
    lexical_only = query_embedding is None or not vector_ranked
    by_id: dict[UUID, StoreHybridCandidate] = {}
    for rank, score, product in lexical_ranked[:50]:
        by_id[product.product_id] = StoreHybridCandidate(
            product=product,
            lexical_rank=rank,
            lexical_score=score,
            lexical_only=lexical_only,
        )
    for rank, score, product in vector_ranked[:50]:
        current = by_id.get(product.product_id)
        by_id[product.product_id] = StoreHybridCandidate(
            product=product,
            lexical_rank=current.lexical_rank if current else None,
            lexical_score=current.lexical_score if current else 0.0,
            vector_rank=rank,
            vector_score=score,
            lexical_only=lexical_only,
        )
    return tuple(by_id.values())


def _rank_lexical(
    products: tuple[StoreProduct, ...], query: str
) -> tuple[tuple[int, float, StoreProduct], ...]:
    scored = [
        (score, product)
        for product in products
        if (score := lexical_score_for_product(product, query)) > 0
    ]
    ranked = sorted(scored, key=lambda item: (-item[0], item[1].metadata.title))
    return tuple((index + 1, score, product) for index, (score, product) in enumerate(ranked))


def _rank_vector(
    products: tuple[StoreProduct, ...],
    query_embedding: tuple[float, ...] | None,
    embeddings: EmbeddingService | None,
) -> tuple[tuple[int, float, StoreProduct], ...]:
    if query_embedding is None:
        return ()
    embed = _product_embedder(embeddings)
    scored = []
    for product in products:
        vector = embed(product_semantic_text(product))
        if vector is None:
            continue
        scored.append((cosine_similarity(query_embedding, vector), product))
    ranked = sorted(scored, key=lambda item: (-item[0], item[1].metadata.title))
    return tuple(
        (index + 1, score, product) for index, (score, product) in enumerate(ranked) if score > 0
    )


def _product_embedder(
    embeddings: EmbeddingService | None,
) -> Callable[[str], tuple[float, ...] | None]:
    if embeddings is not None:
        return lambda text: embeddings.embed(text, purpose="rfi-memory-candidate")
    return MockEmbeddingProvider().embed
