from coeus.core.errors import AppError
from coeus.domain.auth import UserAccount
from coeus.domain.search_index import GroundedProductEvidence
from coeus.domain.store import StoreHybridCandidate
from coeus.services.store_access import StoreDetailService


def merge_grounded_candidates(
    actor: UserAccount,
    details: StoreDetailService,
    candidates: tuple[StoreHybridCandidate, ...],
    evidence: tuple[GroundedProductEvidence, ...],
) -> tuple[StoreHybridCandidate, ...]:
    merged = {candidate.product.product_id: candidate for candidate in candidates}
    for item in evidence:
        existing = merged.get(item.product_id)
        if existing is not None:
            merged[item.product_id] = StoreHybridCandidate(
                product=existing.product,
                lexical_rank=item.lexical_rank or existing.lexical_rank,
                lexical_score=max(item.lexical_score, existing.lexical_score),
                vector_rank=item.vector_rank or existing.vector_rank,
                vector_score=max(item.vector_score, existing.vector_score),
                lexical_only=item.vector_rank is None,
            )
            continue
        try:
            product = details.get_visible_product(actor, item.product_id)
        except AppError:
            continue
        merged[item.product_id] = StoreHybridCandidate(
            product=product,
            lexical_rank=item.lexical_rank,
            lexical_score=item.lexical_score,
            vector_rank=item.vector_rank,
            vector_score=item.vector_score,
            lexical_only=item.vector_rank is None,
        )
    return tuple(
        sorted(
            merged.values(),
            key=lambda item: (
                item.lexical_rank or 9_999,
                item.vector_rank or 9_999,
                item.product.metadata.title,
            ),
        )
    )
