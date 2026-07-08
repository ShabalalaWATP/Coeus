from math import sqrt
from re import findall

from coeus.domain.store import StoreHybridCandidate, StoreProduct, StoreSearchHit
from coeus.domain.tickets import IntakeDetails, ProductOffer, ProductOfferStatus
from coeus.services.store_semantics import product_semantic_text, semantic_label_reasons

RFI_OFFER_THRESHOLD = 0.34
RFI_MAX_OFFERS = 5
RRF_K = 60
LEXICAL_SCORE_FLOOR = 0.12
VECTOR_SIMILARITY_FLOOR = 0.18
STOP_WORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "for",
        "in",
        "is",
        "mock",
        "of",
        "on",
        "or",
        "synthetic",
        "the",
        "to",
        "what",
        "with",
    }
)


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
    query_tokens = _tokens(query_text(intake))
    query = query_text(intake)
    if not query_tokens:
        return ()
    scored: list[tuple[StoreHybridCandidate, float, tuple[str, ...]]] = []
    available_legs = _available_legs(candidates)
    for candidate in candidates:
        text_score, text_reasons = _full_text_score(candidate.product, query_tokens)
        token_score, token_reasons = _semantic_score(candidate.product, query_tokens)
        metadata_score, metadata_reasons = _metadata_score(candidate.product, intake)
        label_score, label_reasons = _semantic_label_score(candidate.product, query)
        score = min(1.0, _rrf_score(candidate, available_legs) + metadata_score + label_score)
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
            intake.operational_question,
            intake.area_or_region,
            intake.known_context,
            intake.required_output_format,
            intake.customer_success_criteria,
        )
        if value
    )


def tokenize(text: str) -> tuple[str, ...]:
    """Canonical retrieval tokeniser shared by every lexical scoring path."""
    return tuple(
        dict.fromkeys(
            token
            for token in findall(r"[a-z0-9]+", text.casefold())
            if len(token) >= 2 and token not in STOP_WORDS
        )
    )


def token_overlap(left: str, right: str) -> bool:
    return bool(set(tokenize(left)).intersection(tokenize(right)))


def _tokens(text: str) -> tuple[str, ...]:
    return tokenize(text)


def _matched_tokens(query_tokens: tuple[str, ...], document: str) -> tuple[str, ...]:
    document_text = document.casefold()
    return tuple(token for token in query_tokens if token in document_text)


def lexical_text_score(query: str, document: str) -> float:
    """Fraction of distinct query tokens present in ``document``.

    This is the single lexical scoring formula, calibrated against
    ``LEXICAL_SCORE_FLOOR``. Both RFI product ranking and similar-request
    ranking route through it so equivalent text scores identically.
    """
    query_tokens = tokenize(query)
    if not query_tokens:
        return 0.0
    matches = _matched_tokens(query_tokens, document)
    return min(len(matches) / len(query_tokens), 1.0)


def _product_text(product: StoreProduct) -> str:
    return product_semantic_text(product)


def lexical_score_for_product(product: StoreProduct, query: str) -> float:
    return lexical_text_score(query, _product_text(product))


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
    product_tokens = set(_tokens(_product_text(product)))
    overlap = tuple(token for token in query_tokens if token in product_tokens)
    denominator = sqrt(max(len(query_tokens), 1) * max(len(product_tokens), 1))
    score = len(overlap) / denominator
    return min(score, 1.0), tuple(f"semantic:{token}" for token in overlap)


def _metadata_score(product: StoreProduct, intake: IntakeDetails) -> tuple[float, tuple[str, ...]]:
    metadata = product.metadata
    reasons: list[str] = []
    score = 0.0
    if intake.area_or_region and token_overlap(intake.area_or_region, metadata.area_or_region):
        score += 0.04
        reasons.append("metadata:region")
    if intake.required_output_format and token_overlap(
        intake.required_output_format,
        metadata.product_type,
    ):
        score += 0.02
        reasons.append("metadata:format")
    return min(score, 0.06), tuple(reasons)


def _semantic_label_score(product: StoreProduct, query: str) -> tuple[float, tuple[str, ...]]:
    reasons = semantic_label_reasons(product, query)
    return min(0.04, len(reasons) * 0.02), reasons


def _available_legs(candidates: tuple[StoreHybridCandidate, ...]) -> int:
    lexical = any(
        candidate.lexical_rank is not None and candidate.lexical_score >= LEXICAL_SCORE_FLOOR
        for candidate in candidates
    )
    vector = any(
        candidate.vector_rank is not None and candidate.vector_score >= VECTOR_SIMILARITY_FLOOR
        for candidate in candidates
    )
    return max(1, int(lexical) + int(vector))


def _rrf_score(candidate: StoreHybridCandidate, available_legs: int) -> float:
    raw = 0.0
    if candidate.lexical_rank is not None and candidate.lexical_score >= LEXICAL_SCORE_FLOOR:
        raw += 1 / (RRF_K + candidate.lexical_rank)
    if candidate.vector_rank is not None and candidate.vector_score >= VECTOR_SIMILARITY_FLOOR:
        raw += 1 / (RRF_K + candidate.vector_rank)
    max_possible = available_legs / (RRF_K + 1)
    return raw / max_possible if max_possible else 0.0


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
