from dataclasses import replace

from coeus.domain.search_relevance import VECTOR_SIMILARITY_FLOOR
from coeus.domain.store import StoreHybridCandidate
from coeus.domain.store_ranking import lexical_score_for_product
from coeus.services.store_search_results import hybrid_hits
from store_projection_helpers import seed_product


def test_hybrid_hits_exclude_zero_signal_query_candidates() -> None:
    product = seed_product()

    hits = hybrid_hits((StoreHybridCandidate(product=product),), "assessment")

    assert hits == ()


def test_hybrid_hits_include_lexical_only_candidates_without_visible_fallback() -> None:
    product = seed_product()

    hits = hybrid_hits(
        (
            StoreHybridCandidate(
                product=product,
                lexical_rank=1,
                lexical_score=0.5,
                lexical_only=True,
            ),
        ),
        "assessment",
    )

    assert len(hits) == 1
    assert "lexical-rank:1" in hits[0].match_reasons
    assert "retrieval:lexical-only" in hits[0].match_reasons
    assert "visible" not in hits[0].match_reasons


def test_hybrid_hits_apply_shared_vector_floor() -> None:
    product = seed_product()

    below = hybrid_hits(
        (
            StoreHybridCandidate(
                product=product,
                vector_rank=1,
                vector_score=VECTOR_SIMILARITY_FLOOR - 0.01,
            ),
        ),
        "assessment",
    )
    at_floor = hybrid_hits(
        (
            StoreHybridCandidate(
                product=product,
                vector_rank=1,
                vector_score=VECTOR_SIMILARITY_FLOOR,
            ),
        ),
        "assessment",
    )

    assert below == ()
    assert len(at_floor) == 1
    assert f"vector-similarity:{VECTOR_SIMILARITY_FLOOR:.2f}" in at_floor[0].match_reasons


def test_exact_title_outranks_a_summary_only_mention() -> None:
    base = seed_product()
    exact = replace(base, metadata=replace(base.metadata, title="Russia Electronic Warfare"))
    summary_only = replace(
        base,
        product_id=__import__("uuid").uuid4(),
        metadata=replace(
            base.metadata,
            title="Regional Activity Digest",
            summary="MOCK DATA ONLY Russia electronic warfare reporting.",
        ),
    )

    assert lexical_score_for_product(exact, "Russia Electronic Warfare") == 1.0
    assert lexical_score_for_product(exact, "Russia Electronic Warfare") > (
        lexical_score_for_product(summary_only, "Russia Electronic Warfare")
    )
