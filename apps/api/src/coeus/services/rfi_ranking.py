from datetime import date
from math import sqrt

from coeus.domain.search_relevance import (
    LEXICAL_SCORE_FLOOR,
    RRF_K,
    VECTOR_SIMILARITY_FLOOR,
    available_hybrid_legs,
    hybrid_rrf_score,
    matched_tokens,
)
from coeus.domain.store import StoreHybridCandidate, StoreProduct, StoreSearchHit
from coeus.domain.store_ranking import (
    lexical_score_for_product,
    lexical_text_score,
    token_overlap,
    tokenize,
)
from coeus.domain.tickets import IntakeDetails, ProductOffer, ProductOfferStatus
from coeus.services.store_semantics import product_semantic_text, semantic_label_reasons

RFI_OFFER_THRESHOLD = 0.20
RFI_MAX_OFFERS = 5
RFI_RANKING_WORK_LIMIT = 100
__all__ = [
    "LEXICAL_SCORE_FLOOR",
    "RRF_K",
    "VECTOR_SIMILARITY_FLOOR",
    "lexical_score_for_product",
    "lexical_text_score",
    "query_text",
    "rank_hybrid_rfi_candidates",
    "rank_rfi_hits",
    "token_overlap",
    "tokenize",
]


def rank_rfi_hits(
    hits: tuple[StoreSearchHit, ...],
    intake: IntakeDetails,
) -> tuple[ProductOffer, ...]:
    query = query_text(intake)
    lexical_hits = [(lexical_score_for_product(hit.product, query), hit.product) for hit in hits]
    candidates = tuple(
        StoreHybridCandidate(
            product=product,
            lexical_rank=index + 1,
            lexical_score=score,
            lexical_only=True,
        )
        for index, (score, product) in enumerate(
            sorted(
                (
                    (score, product)
                    for score, product in lexical_hits
                    if score >= LEXICAL_SCORE_FLOOR
                ),
                key=lambda item: (-item[0], item[1].metadata.title),
            )
        )
    )
    return rank_hybrid_rfi_candidates(candidates, intake)


def rank_hybrid_rfi_candidates(
    candidates: tuple[StoreHybridCandidate, ...],
    intake: IntakeDetails,
) -> tuple[ProductOffer, ...]:
    query = query_text(intake)
    query_tokens = _tokens(query)
    if not query_tokens:
        return ()
    scored: list[tuple[StoreHybridCandidate, float, tuple[str, ...]]] = []
    bounded_candidates = candidates[:RFI_RANKING_WORK_LIMIT]
    available_legs = _available_legs(bounded_candidates)
    for candidate in bounded_candidates:
        product_text = _product_text(candidate.product)
        product_tokens = _tokens(product_text)
        text_score, text_reasons = _score_tokens(query_tokens, product_tokens, "full-text")
        token_score, token_reasons = _semantic_score_from_tokens(query_tokens, product_tokens)
        metadata_score, metadata_reasons = _metadata_score(candidate.product, intake, product_text)
        label_score, label_reasons = _semantic_label_score(candidate.product, query)
        title_signal = lexical_score_for_product(candidate.product, intake.title or "")
        lexical_signal = max(text_score, candidate.lexical_score, title_signal)
        vector_signal = max(
            0.0,
            (candidate.vector_score - VECTOR_SIMILARITY_FLOOR) / (1.0 - VECTOR_SIMILARITY_FLOOR),
        )
        # Rank fusion is only a small ordering signal. Absolute lexical and
        # vector evidence determine whether an offer is relevant enough.
        score = min(
            1.0,
            (0.50 * lexical_signal)
            + (0.35 * vector_signal)
            + (0.05 * _rrf_score(candidate, available_legs))
            + metadata_score
            + label_score,
        )
        reasons = _reasons(
            candidate,
            label_reasons,
            text_reasons,
            token_reasons,
            metadata_reasons,
            text_score,
            token_score,
        )
        if score >= RFI_OFFER_THRESHOLD:
            scored.append((candidate, round(score, 4), tuple(dict.fromkeys(reasons))))
    ranked = sorted(scored, key=lambda item: (-item[1], item[0].product.metadata.title))
    return tuple(
        _offer(candidate.product, score, reasons)
        for candidate, score, reasons in ranked[:RFI_MAX_OFFERS]
    )


def query_text(intake: IntakeDetails) -> str:
    return " ".join(
        value
        for value in (
            intake.title,
            intake.description,
            intake.operational_question,
            intake.area_or_region,
            intake.known_context,
            intake.required_output_format,
            intake.customer_success_criteria,
            intake.intelligence_disciplines,
            intake.supported_operation,
            intake.time_period_start,
            intake.time_period_end,
            intake.priority,
            intake.deadline,
            intake.restrictions_or_caveats,
            intake.suggested_acg_context,
            intake.requesting_unit,
            intake.urgency_justification,
        )
        if value
    )


def _tokens(text: str) -> tuple[str, ...]:
    return tokenize(text)


def _matched_tokens(query_tokens: tuple[str, ...], document: str) -> tuple[str, ...]:
    return matched_tokens(query_tokens, tokenize(document))


def _product_text(product: StoreProduct) -> str:
    return product_semantic_text(product)


def _full_text_score(
    product: StoreProduct,
    query_tokens: tuple[str, ...],
) -> tuple[float, tuple[str, ...]]:
    if not query_tokens:
        return 0.0, ()
    matches = _matched_tokens(query_tokens, _product_text(product))
    score = len(matches) / len(query_tokens)
    return min(score, 1.0), tuple(f"full-text:{token}" for token in matches)


def _semantic_score(
    product: StoreProduct,
    query_tokens: tuple[str, ...],
) -> tuple[float, tuple[str, ...]]:
    if not query_tokens:
        return 0.0, ()
    product_tokens = _tokens(_product_text(product))
    overlap = matched_tokens(query_tokens, product_tokens)
    denominator = sqrt(max(len(query_tokens), 1) * max(len(product_tokens), 1))
    score = len(overlap) / denominator
    return min(score, 1.0), tuple(f"semantic:{token}" for token in overlap)


def _score_tokens(
    query_tokens: tuple[str, ...], product_tokens: tuple[str, ...], prefix: str
) -> tuple[float, tuple[str, ...]]:
    matches = matched_tokens(query_tokens, product_tokens)
    score = len(matches) / len(query_tokens) if query_tokens else 0.0
    return min(score, 1.0), tuple(f"{prefix}:{token}" for token in matches)


def _semantic_score_from_tokens(
    query_tokens: tuple[str, ...], product_tokens: tuple[str, ...]
) -> tuple[float, tuple[str, ...]]:
    overlap = matched_tokens(query_tokens, product_tokens)
    denominator = sqrt(max(len(query_tokens), 1) * max(len(product_tokens), 1))
    score = len(overlap) / denominator
    return min(score, 1.0), tuple(f"semantic:{token}" for token in overlap)


def _metadata_score(
    product: StoreProduct, intake: IntakeDetails, product_text: str
) -> tuple[float, tuple[str, ...]]:
    metadata = product.metadata
    reasons: list[str] = []
    score = 0.0
    if intake.area_or_region and token_overlap(intake.area_or_region, metadata.area_or_region):
        score += 0.05
        reasons.append("metadata:region")
    if intake.required_output_format and token_overlap(
        intake.required_output_format,
        metadata.product_type,
    ):
        score += 0.03
        reasons.append("metadata:format")
    if intake.supported_operation and token_overlap(intake.supported_operation, product_text):
        score += 0.04
        reasons.append("metadata:operation")
    if intake.intelligence_disciplines and token_overlap(
        intake.intelligence_disciplines, product_text
    ):
        score += 0.04
        reasons.append("metadata:discipline")
    if intake.requesting_unit and token_overlap(intake.requesting_unit, metadata.owner_team):
        score += 0.02
        reasons.append("metadata:requesting-unit")
    temporal_score, temporal_reason = _temporal_score(product, intake)
    score += temporal_score
    if temporal_reason:
        reasons.append(temporal_reason)
    return max(-0.12, min(score, 0.24)), tuple(reasons)


def _temporal_score(product: StoreProduct, intake: IntakeDetails) -> tuple[float, str | None]:
    requested_start = _date(intake.time_period_start)
    requested_end = _date(intake.time_period_end)
    product_start = _date(product.metadata.time_period_start)
    product_end = _date(product.metadata.time_period_end) or product_start
    if not requested_start and not requested_end:
        return 0.0, None
    if not product_start:
        return 0.0, "metadata:time-unknown"
    effective_request_start = requested_start or requested_end
    effective_request_end = requested_end or requested_start
    if effective_request_start and effective_request_end and product_end:
        overlaps = product_end >= effective_request_start and product_start <= effective_request_end
        return (0.08, "metadata:time-overlap") if overlaps else (-0.12, "metadata:time-mismatch")
    return 0.0, None


def _date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _semantic_label_score(product: StoreProduct, query: str) -> tuple[float, tuple[str, ...]]:
    reasons = semantic_label_reasons(product, query)
    return min(0.04, len(reasons) * 0.02), reasons


def _available_legs(candidates: tuple[StoreHybridCandidate, ...]) -> int:
    return available_hybrid_legs(candidates)


def _rrf_score(candidate: StoreHybridCandidate, available_legs: int) -> float:
    return hybrid_rrf_score(candidate, available_legs)


def _reasons(
    candidate: StoreHybridCandidate,
    label_reasons: tuple[str, ...],
    text_reasons: tuple[str, ...],
    token_reasons: tuple[str, ...],
    metadata_reasons: tuple[str, ...],
    text_score: float,
    token_score: float,
) -> tuple[str, ...]:
    rank_reasons = []
    if candidate.lexical_rank is not None and candidate.lexical_score >= LEXICAL_SCORE_FLOOR:
        rank_reasons.append(f"lexical-rank:{candidate.lexical_rank}")
    if candidate.vector_rank is not None and candidate.vector_score >= VECTOR_SIMILARITY_FLOOR:
        rank_reasons.append(f"vector-similarity:{candidate.vector_score:.2f}")
    if candidate.lexical_only:
        rank_reasons.append("retrieval:lexical-only")
    score_reasons: list[str] = []
    if text_score > 0:
        score_reasons.extend(text_reasons[:3])
    if token_score > 0:
        score_reasons.extend(token_reasons[:2])
    return (
        *rank_reasons,
        *label_reasons,
        *score_reasons,
        *metadata_reasons,
    )


def _offer(product: StoreProduct, score: float, reasons: tuple[str, ...]) -> ProductOffer:
    metadata = product.metadata
    return ProductOffer(
        product_id=product.product_id,
        title=metadata.title,
        summary=metadata.summary,
        product_type=metadata.product_type,
        match_score=score,
        match_reasons=reasons,
        classification_level=metadata.classification_level,
        releasability=tuple(sorted(metadata.releasability)),
        region=metadata.area_or_region,
        time_period_start=metadata.time_period_start,
        time_period_end=metadata.time_period_end,
        asset_types=tuple(sorted({asset.asset_type for asset in product.assets})),
        offerable_to_user=True,
        status=ProductOfferStatus.OFFERED,
    )
