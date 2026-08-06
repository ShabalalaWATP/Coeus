"""Offers are ordered by whether the report text answers the request."""

from dataclasses import replace
from uuid import uuid4

from coeus.domain.search_index import SearchPassage
from coeus.domain.store import StoreHybridCandidate, StoreProduct
from coeus.domain.tickets import IntakeDetails
from coeus.services.rfi_content_relevance import content_relevance
from coeus.services.rfi_ranking import rank_hybrid_rfi_candidates
from store_projection_helpers import seed_product

INTAKE = IntakeDetails(
    title="Port infrastructure damage assessment",
    operational_question="What damage has been done to the port cranes and berths?",
    area_or_region="Baltic",
)


def _product(title: str) -> StoreProduct:
    product = seed_product()
    return replace(
        product,
        product_id=uuid4(),
        metadata=replace(
            product.metadata,
            title=title,
            summary="Baltic maritime reporting.",
            description="Synthetic maritime report.",
            area_or_region="Baltic",
            semantic_labels=frozenset(),
        ),
    )


def _passage(product_id: object, excerpt: str) -> SearchPassage:
    return SearchPassage(
        product_id=product_id,  # type: ignore[arg-type]
        chunk_id=uuid4(),
        asset_id=uuid4(),
        asset_name="report.pdf",
        page_number=4,
        excerpt=excerpt,
        lexical_score=0.5,
        vector_score=0.5,
        lexical_rank=1,
        vector_rank=1,
    )


def _candidate(product: StoreProduct) -> StoreHybridCandidate:
    return StoreHybridCandidate(
        product=product, lexical_rank=1, lexical_score=0.4, vector_rank=1, vector_score=0.8
    )


def test_the_report_whose_text_answers_the_question_is_offered_first() -> None:
    # Both products look alike from their metadata. Only the passages separate the
    # report that addresses the cranes and berths from the one that does not.
    on_topic = _product("Baltic Maritime Report")
    off_topic = _product("Baltic Maritime Digest")
    passages = {
        off_topic.product_id: (
            _passage(off_topic.product_id, "Weather patterns and sea state across the region."),
        ),
        on_topic.product_id: (
            _passage(
                on_topic.product_id,
                "Damage to the port cranes was extensive and two berths remain unusable.",
            ),
        ),
    }

    offers = rank_hybrid_rfi_candidates(
        (_candidate(off_topic), _candidate(on_topic)), INTAKE, passages=passages
    )

    assert offers[0].title == "Baltic Maritime Report"
    assert offers[0].match_score > offers[1].match_score


def test_a_content_match_is_explained_in_the_offer_reasons() -> None:
    product = _product("Baltic Maritime Report")
    passages = {
        product.product_id: (
            _passage(
                product.product_id,
                "Damage to the port cranes and berths is assessed in detail.",
            ),
        )
    }

    offers = rank_hybrid_rfi_candidates((_candidate(product),), INTAKE, passages=passages)

    assert any(reason.startswith("content:") for reason in offers[0].match_reasons)
    assert "content:answers-question" in offers[0].match_reasons


def test_ranking_without_passages_keeps_the_metadata_only_weighting() -> None:
    # Metadata-only retrieval must be unaffected, so a corpus with no indexed
    # passages ranks exactly as it did before content scoring existed.
    product = _product("Port infrastructure damage assessment")

    with_none = rank_hybrid_rfi_candidates((_candidate(product),), INTAKE)
    with_empty = rank_hybrid_rfi_candidates((_candidate(product),), INTAKE, passages={})

    assert with_none[0].match_score == with_empty[0].match_score
    assert not any(reason.startswith("content:") for reason in with_none[0].match_reasons)


def test_content_score_rewards_the_question_over_incidental_overlap() -> None:
    query_tokens = ("port", "cranes", "berths", "damage", "baltic")
    question_tokens = ("port", "cranes", "berths", "damage")
    answering = (_passage(uuid4(), "port cranes and berths sustained damage"),)
    incidental = (_passage(uuid4(), "baltic shipping lanes remain open"),)

    answering_score, answering_reasons = content_relevance(answering, query_tokens, question_tokens)
    incidental_score, _ = content_relevance(incidental, query_tokens, question_tokens)

    assert answering_score > incidental_score
    assert "content:answers-question" in answering_reasons


def test_empty_passage_text_scores_nothing() -> None:
    query_tokens = ("port", "cranes")

    score, reasons = content_relevance((_passage(uuid4(), "   "),), query_tokens, query_tokens)

    assert score == 0.0
    assert reasons == ()
