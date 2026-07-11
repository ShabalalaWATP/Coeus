from collections.abc import Callable
from uuid import UUID

from coeus.domain.search_relevance import VECTOR_SIMILARITY_FLOOR
from coeus.domain.store import StoreHybridCandidate, StoreProduct, StoreSearchFilters
from coeus.domain.store_filters import structured_filter_match
from coeus.services.embeddings import EmbeddingService, MockEmbeddingProvider, cosine_similarity
from coeus.services.rfi_ranking import lexical_score_for_product
from coeus.services.store_semantics import product_semantic_text

MEMORY_VECTOR_WORK_LIMIT = 64


def memory_hybrid_candidates(
    products: tuple[StoreProduct, ...],
    query: str,
    query_embedding: tuple[float, ...] | None,
    embeddings: EmbeddingService | None = None,
    filters: StoreSearchFilters | None = None,
    leg_limit: int = 50,
) -> tuple[StoreHybridCandidate, ...]:
    """Return deterministic hybrid candidates when no PostgreSQL projection exists.

    Product vectors come from the same provider as the query vector when an
    ``EmbeddingService`` is supplied, so the cosine comparison stays inside one
    embedding space. Without a service the deterministic mock provider is used,
    which matches the default local configuration where the query vector is also
    a mock vector. Callers should pass the configured service under a non-mock
    provider to avoid comparing vectors from two different embedding spaces.
    """

    filtered_products = _structured_products(products, filters)
    lexical_ranked = _rank_lexical(filtered_products, query)
    # The memory fallback has no persisted vector index. Bound its candidate
    # work independently of corpus size, using lexical order as a deterministic
    # preselection before the optional semantic leg.
    vector_products = tuple(item[2] for item in lexical_ranked[:MEMORY_VECTOR_WORK_LIMIT])
    if len(vector_products) < MEMORY_VECTOR_WORK_LIMIT:
        selected = {product.product_id for product in vector_products}
        supplements = (
            product
            for product in sorted(filtered_products, key=lambda item: item.metadata.title)
            if product.product_id not in selected
        )
        remaining = MEMORY_VECTOR_WORK_LIMIT - len(vector_products)
        vector_products = (*vector_products, *tuple(supplements)[:remaining])
    vector_ranked = _rank_vector(vector_products, query_embedding, embeddings)
    # A run is effectively lexical-only when the query never embedded or when no
    # candidate produced a usable vector, so the semantic leg contributed nothing.
    lexical_only = query_embedding is None or not vector_ranked
    by_id: dict[UUID, StoreHybridCandidate] = {}
    for rank, score, product in lexical_ranked[:leg_limit]:
        by_id[product.product_id] = StoreHybridCandidate(
            product=product,
            lexical_rank=rank,
            lexical_score=score,
            lexical_only=lexical_only,
        )
    for rank, score, product in vector_ranked[:leg_limit]:
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
        (index + 1, score, product)
        for index, (score, product) in enumerate(ranked)
        if score >= VECTOR_SIMILARITY_FLOOR
    )


def _structured_products(
    products: tuple[StoreProduct, ...],
    filters: StoreSearchFilters | None,
) -> tuple[StoreProduct, ...]:
    if filters is None:
        return products
    return tuple(product for product in products if structured_filter_match(product, filters))


def _product_embedder(
    embeddings: EmbeddingService | None,
) -> Callable[[str], tuple[float, ...] | None]:
    if embeddings is not None:
        cached = getattr(embeddings, "embed_cached", None)
        if cached is not None:
            return lambda text: cached(text, purpose="memory-candidate")
        return lambda text: embeddings.embed(text, purpose="memory-candidate")
    return MockEmbeddingProvider().embed
