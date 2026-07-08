from dataclasses import replace

from coeus.domain.store import StoreHybridCandidate, StoreSearchHit
from coeus.domain.tickets import IntakeDetails
from coeus.services.embeddings import MockEmbeddingProvider, cosine_similarity
from coeus.services.rfi_ranking import (
    LEXICAL_SCORE_FLOOR,
    lexical_score_for_product,
    query_text,
    rank_hybrid_rfi_candidates,
    rank_rfi_hits,
)
from coeus.services.store_semantics import product_semantic_text
from store_projection_helpers import seed_product


def test_mock_semantic_leg_finds_different_vocabulary_when_lexical_does_not() -> None:
    provider = MockEmbeddingProvider()
    product = seed_product()
    product = replace(
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
    intake = IntakeDetails(
        title="Boat traffic near St Petersburg",
        operational_question="What boat traffic is near St Petersburg?",
        area_or_region="St Petersburg",
        required_output_format="traffic picture",
    )
    query = query_text(intake)
    score = cosine_similarity(provider.embed(query), provider.embed(product_semantic_text(product)))

    lexical_offers = rank_rfi_hits((StoreSearchHit(product, 0.0, ()),), intake)
    semantic_offers = rank_hybrid_rfi_candidates(
        (StoreHybridCandidate(product=product, vector_rank=1, vector_score=score),),
        intake,
    )

    assert lexical_score_for_product(product, query) == 0
    assert lexical_offers == ()
    assert semantic_offers[0].title == "Vessel Movements, Gulf of Finland"
    assert any(
        reason.startswith("vector-similarity:") for reason in semantic_offers[0].match_reasons
    )


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
