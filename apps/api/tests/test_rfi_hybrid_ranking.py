from dataclasses import replace

import pytest

from coeus.domain.store import StoreHybridCandidate, StoreProduct, StoreSearchHit
from coeus.domain.tickets import IntakeDetails
from coeus.services.rfi_ranking import (
    LEXICAL_SCORE_FLOOR,
    _date,
    _full_text_score,
    _metadata_score,
    _semantic_score,
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


def test_empty_query_tokens_have_no_lexical_or_semantic_score() -> None:
    product = seed_product()

    assert _full_text_score(product, ()) == (0.0, ())
    assert _semantic_score(product, ()) == (0.0, ())


def test_non_empty_lexical_semantic_and_operational_metadata_scores() -> None:
    original = seed_product()
    product = replace(
        original,
        metadata=replace(
            original.metadata,
            title="Operation Rowan imagery assessment",
            description="Synthetic GEOINT reporting for Operation Rowan.",
            owner_team="Joint Analysis Unit",
        ),
    )
    tokens = ("operation", "rowan", "imagery")

    lexical, lexical_reasons = _full_text_score(product, tokens)
    semantic, semantic_reasons = _semantic_score(product, tokens)
    metadata, metadata_reasons = _metadata_score(
        product,
        IntakeDetails(
            supported_operation="Operation Rowan",
            intelligence_disciplines="GEOINT imagery",
            requesting_unit="Joint Analysis Unit",
        ),
        "Operation Rowan GEOINT imagery reporting",
    )

    assert lexical > 0 and lexical_reasons
    assert semantic > 0 and semantic_reasons
    assert metadata == pytest.approx(0.10)
    assert set(metadata_reasons) == {
        "metadata:operation",
        "metadata:discipline",
        "metadata:requesting-unit",
    }
    assert _date("not-a-date") is None


def test_rank_one_weak_match_is_not_misreported_as_a_confident_offer() -> None:
    original = seed_product()
    product = replace(
        original,
        metadata=replace(
            original.metadata,
            title="Asia-Pacific Shipping Disruption Digest",
            summary="MOCK DATA ONLY maritime port disruption summary.",
            description="Synthetic shipping assessment.",
            tags=frozenset({"shipping", "ports"}),
            semantic_labels=frozenset({"maritime"}),
        ),
    )
    intake = IntakeDetails(
        title="Arctic Army aviation readiness",
        operational_question="What is the readiness of Army aviation in the Arctic?",
        area_or_region="Arctic",
        required_output_format="assessment",
    )
    lexical_score = lexical_score_for_product(product, query_text(intake))

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

    assert offers == ()
