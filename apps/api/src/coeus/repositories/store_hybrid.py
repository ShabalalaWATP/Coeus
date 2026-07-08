from uuid import UUID

from coeus.domain.store import StoreHybridCandidate, StoreProduct
from coeus.services.embeddings import MockEmbeddingProvider, cosine_similarity
from coeus.services.rfi_ranking import lexical_score_for_product
from coeus.services.store_semantics import product_semantic_text


def memory_hybrid_candidates(
    products: tuple[StoreProduct, ...],
    query: str,
    query_embedding: tuple[float, ...] | None,
) -> tuple[StoreHybridCandidate, ...]:
    """Return deterministic hybrid candidates when no PostgreSQL projection exists."""

    lexical_ranked = _rank_lexical(products, query)
    vector_ranked = _rank_vector(products, query_embedding)
    by_id: dict[UUID, StoreHybridCandidate] = {}
    for rank, score, product in lexical_ranked[:50]:
        by_id[product.product_id] = StoreHybridCandidate(
            product=product,
            lexical_rank=rank,
            lexical_score=score,
            lexical_only=query_embedding is None,
        )
    for rank, score, product in vector_ranked[:50]:
        current = by_id.get(product.product_id)
        by_id[product.product_id] = StoreHybridCandidate(
            product=product,
            lexical_rank=current.lexical_rank if current else None,
            lexical_score=current.lexical_score if current else 0.0,
            vector_rank=rank,
            vector_score=score,
            lexical_only=query_embedding is None,
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
) -> tuple[tuple[int, float, StoreProduct], ...]:
    if query_embedding is None:
        return ()
    provider = MockEmbeddingProvider()
    scored = [
        (
            cosine_similarity(query_embedding, provider.embed(product_semantic_text(product))),
            product,
        )
        for product in products
    ]
    ranked = sorted(scored, key=lambda item: (-item[0], item[1].metadata.title))
    return tuple(
        (index + 1, score, product) for index, (score, product) in enumerate(ranked) if score > 0
    )
