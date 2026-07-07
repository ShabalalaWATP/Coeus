from math import sqrt
from re import findall

from coeus.domain.store import StoreProduct, StoreSearchHit
from coeus.domain.tickets import IntakeDetails, ProductOffer, ProductOfferStatus
from coeus.services.store_semantics import product_semantic_text, semantic_label_reasons

RFI_OFFER_THRESHOLD = 0.25
RFI_MAX_OFFERS = 5
STOP_WORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "for",
        "in",
        "is",
        "of",
        "on",
        "or",
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
    query_tokens = _tokens(query_text(intake))
    scored: list[tuple[StoreSearchHit, float, tuple[str, ...]]] = []
    for hit in hits:
        text_score, text_reasons = _full_text_score(hit.product, query_tokens)
        vector_score, vector_reasons = _semantic_score(hit.product, query_tokens)
        metadata_score, metadata_reasons = _metadata_score(hit.product, intake)
        label_score, label_reasons = _semantic_label_score(hit.product, query_text(intake))
        score = min(
            1.0,
            (text_score * 0.38) + (vector_score * 0.34) + metadata_score + label_score,
        )
        reasons = (*label_reasons, *text_reasons[:3], *vector_reasons[:2], *metadata_reasons)
        if score >= RFI_OFFER_THRESHOLD:
            scored.append((hit, round(score, 4), tuple(dict.fromkeys(reasons))))
    ranked = sorted(scored, key=lambda item: (-item[1], item[0].product.metadata.title))
    return tuple(_offer(hit, score, reasons) for hit, score, reasons in ranked[:RFI_MAX_OFFERS])


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


def _tokens(text: str) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            token
            for token in findall(r"[a-z0-9]+", text.casefold())
            if len(token) >= 2 and token not in STOP_WORDS
        )
    )


def _product_text(product: StoreProduct) -> str:
    return product_semantic_text(product)


def _full_text_score(
    product: StoreProduct,
    query_tokens: tuple[str, ...],
) -> tuple[float, tuple[str, ...]]:
    if not query_tokens:
        return 0.0, ()
    product_text = _product_text(product).casefold()
    matches = tuple(token for token in query_tokens if token in product_text)
    score = len(matches) / max(len(query_tokens), 1)
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
    if intake.area_or_region and _token_overlap(intake.area_or_region, metadata.area_or_region):
        score += 0.16
        reasons.append("metadata:region")
    if intake.required_output_format and _token_overlap(
        intake.required_output_format,
        metadata.product_type,
    ):
        score += 0.08
        reasons.append("metadata:format")
    return min(score, 0.24), tuple(reasons)


def _semantic_label_score(product: StoreProduct, query: str) -> tuple[float, tuple[str, ...]]:
    reasons = semantic_label_reasons(product, query)
    return min(0.12, len(reasons) * 0.06), reasons


def _token_overlap(left: str, right: str) -> bool:
    return bool(set(_tokens(left)).intersection(_tokens(right)))


def _offer(hit: StoreSearchHit, score: float, reasons: tuple[str, ...]) -> ProductOffer:
    product = hit.product
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
