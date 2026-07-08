from dataclasses import replace

from coeus.domain.store import StoreHybridCandidate, StoreProduct, StoreSearchHit
from coeus.domain.tickets import IntakeDetails
from coeus.services.rfi_ranking import (
    LEXICAL_SCORE_FLOOR,
    lexical_score_for_product,
    query_text,
    rank_hybrid_rfi_candidates,
    rank_rfi_hits,
)
from store_projection_helpers import seed_product


def _vessel_product() -> StoreProduct:
    product = seed_product()
    return replace(
        product,
        metadata=replace(
            product.metadata,
            title="Vessel Movements, Gulf of Finland",
            summary="MOCK DATA ONLY vessel movements around the Gulf of Finland.",
            description="Synthetic maritime movement report.",
            area_or_region="Gulf of Finland",
            semantic_labels=frozenset(),
        ),
    )


def test_strong_vector_score_surfaces_lexically_disjoint_product() -> None:
    # Mechanism test: given a real provider that judges these two texts close
    # (a vector score no lexical overlap could earn), the fusion and threshold
    # logic must still promote the product to an offer with a vector reason.
    product = _vessel_product()
    intake = IntakeDetails(
        title="Boat traffic near St Petersburg",
        operational_question="What boat traffic is near St Petersburg?",
        area_or_region="St Petersburg",
        required_output_format="traffic picture",
    )
    query = query_text(intake)

    lexical_offers = rank_rfi_hits((StoreSearchHit(product, 0.0, ()),), intake)
    semantic_offers = rank_hybrid_rfi_candidates(
        (StoreHybridCandidate(product=product, vector_rank=1, vector_score=0.9),),
        intake,
    )

    assert lexical_score_for_product(product, query) == 0
    assert lexical_offers == ()
    assert semantic_offers[0].title == "Vessel Movements, Gulf of Finland"
    assert any(
        reason.startswith("vector-similarity:") for reason in semantic_offers[0].match_reasons
    )


def test_lexical_only_candidate_emits_retrieval_reason() -> None:
    # A candidate flagged lexical-only (no usable semantic leg) still produces an
    # offer, tagged so the caller can see retrieval degraded to lexical ranking.
    product = _vessel_product()
    intake = IntakeDetails(
        title="Vessel movements Gulf of Finland",
        operational_question="Report vessel movements in the Gulf of Finland.",
        area_or_region="Gulf of Finland",
    )
    score = lexical_score_for_product(product, query_text(intake))

    offers = rank_hybrid_rfi_candidates(
        (
            StoreHybridCandidate(
                product=product,
                lexical_rank=1,
                lexical_score=score,
                lexical_only=True,
            ),
        ),
        intake,
    )

    assert score >= LEXICAL_SCORE_FLOOR
    assert offers
    assert "retrieval:lexical-only" in offers[0].match_reasons


def test_synthetic_boilerplate_terms_do_not_create_lexical_offer() -> None:
    product = seed_product()
    intake = IntakeDetails(
        title="Mock crop forecast",
        operational_question="What crop yield is expected?",
        area_or_region="Mars farms",
        required_output_format="spreadsheet",
        customer_success_criteria="Estimate crop output.",
    )
    query = query_text(intake)
    lexical_score = lexical_score_for_product(product, query)
    offers = rank_hybrid_rfi_candidates(
        (
            StoreHybridCandidate(
                product=product,
                lexical_rank=1,
                lexical_score=lexical_score,
                lexical_only=True,
            ),
        ),
        intake,
    )

    assert lexical_score < LEXICAL_SCORE_FLOOR
    assert offers == ()
