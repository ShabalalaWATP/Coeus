from typing import cast
from uuid import uuid4

from coeus.domain.enums import TicketState
from coeus.domain.tickets import IntakeDetails, TicketRecord
from coeus.services.embeddings import EmbeddingService
from coeus.services.rfi_ranking import lexical_score_for_product, lexical_text_score
from coeus.services.similar_request_scoring import score_similar_requests
from coeus.services.store_semantics import product_semantic_text
from store_projection_helpers import seed_product


class NoEmbeddingService:
    def embed_cached(self, _text: str, *, purpose: str, principal_id: object | None = None) -> None:
        return None


class FixedEmbeddingService:
    def __init__(self, candidate_vector: tuple[float, ...] | None = (0.2, 0.4)) -> None:
        self.calls = 0
        self.candidate_vector = candidate_vector

    def embed_cached(
        self, _text: str, *, purpose: str, principal_id: object | None = None
    ) -> tuple[float, ...] | None:
        self.calls += 1
        return (0.2, 0.4) if self.calls == 1 else self.candidate_vector


def test_similar_and_rfi_paths_share_one_lexical_scorer() -> None:
    # Part B (similar requests) must score equivalent text identically to Part A
    # (RFI product ranking); both now route through the shared formula, so the
    # floor stays calibrated and results cannot drift apart.
    product = seed_product()
    document = product_semantic_text(product)
    query = "Baltic regional stability assessment ports"

    assert lexical_score_for_product(product, query) == lexical_text_score(query, document)


def test_score_similar_requests_returns_empty_when_no_open_candidates() -> None:
    source = _ticket("Maritime source", state=TicketState.RFI_SEARCHING)
    closed = _ticket("Maritime closed", state=TicketState.CLOSED_DELIVERED)

    embeddings = cast(EmbeddingService, NoEmbeddingService())

    assert score_similar_requests(source, (source, closed), embeddings, 0.0) == ()


def test_score_similar_requests_degrades_to_lexical_only_when_embeddings_are_unavailable() -> None:
    source = _ticket(
        "Gulf of Finland vessel activity",
        region="Gulf of Finland",
        output_format="movement report",
    )
    candidate = _ticket(
        None,
        question="Report vessel activity and shipping movements in the Gulf of Finland.",
        region="Gulf of Finland",
        output_format="movement report",
    )

    matches = score_similar_requests(
        source, (candidate,), cast(EmbeddingService, NoEmbeddingService()), 0.0
    )

    assert matches[0].ticket_id == candidate.ticket_id
    assert matches[0].title == "Untitled requirement"
    assert "similarity:lexical-only" in matches[0].reasons
    assert "similarity:metadata-region" in matches[0].reasons
    assert "similarity:metadata-format" in matches[0].reasons


def test_plural_variant_duplicate_crosses_manager_similarity_threshold() -> None:
    # Every content token differs only by plural inflection, so this match
    # exists solely because of stem folding; it must fail if folding regresses.
    source = _ticket(
        "Sensor radar deployment",
        question="Sensor and radar deployment covering port approach.",
    )
    candidate = _ticket(
        "Sensors radars deployments",
        question="Sensors and radars deployments coverings ports approaches.",
    )

    matches = score_similar_requests(
        source, (candidate,), cast(EmbeddingService, NoEmbeddingService()), 0.50
    )

    assert matches[0].ticket_id == candidate.ticket_id
    assert matches[0].score >= 0.50
    assert "similarity:lexical-rank:1" in matches[0].reasons


def test_no_match_tickets_are_still_open_similarity_candidates() -> None:
    source = _ticket("Gulf of Finland vessel activity")
    candidate = _ticket(
        "Gulf of Finland shipping activity",
        state=TicketState.RFI_NO_MATCH,
    )

    matches = score_similar_requests(
        source, (candidate,), cast(EmbeddingService, NoEmbeddingService()), 0.0
    )

    assert matches[0].ticket_id == candidate.ticket_id
    assert matches[0].state == TicketState.RFI_NO_MATCH


def test_similarity_scoring_supports_vector_only_and_missing_candidate_vectors() -> None:
    source = _ticket("Unrelated source words")
    vector_candidate = _ticket("Distinct candidate vocabulary")
    vector_matches = score_similar_requests(
        source,
        (vector_candidate,),
        cast(EmbeddingService, FixedEmbeddingService()),
        0.0,
    )

    assert vector_matches[0].reasons[0].startswith("similarity:vector:")
    assert not any("lexical" in reason for reason in vector_matches[0].reasons)

    lexical_candidate = _ticket("Unrelated source words")
    lexical_matches = score_similar_requests(
        source,
        (lexical_candidate,),
        cast(EmbeddingService, FixedEmbeddingService(candidate_vector=None)),
        0.0,
    )
    assert "similarity:lexical-only" in lexical_matches[0].reasons


def test_similarity_embedding_work_is_bounded_for_large_candidate_corpus() -> None:
    source = _ticket("Maritime source")
    candidates = tuple(_ticket(f"Candidate {index}") for index in range(101))
    embeddings = FixedEmbeddingService()

    score_similar_requests(source, candidates, cast(EmbeddingService, embeddings), 0.0)

    # One query plus the fixed semantic candidate budget.
    assert embeddings.calls == 33


def _ticket(
    title: str | None,
    *,
    question: str | None = None,
    region: str | None = None,
    output_format: str | None = None,
    state: TicketState = TicketState.RFI_SEARCHING,
) -> TicketRecord:
    return TicketRecord(
        ticket_id=uuid4(),
        reference=f"COEUS-{uuid4().hex[:6]}",
        requester_user_id=uuid4(),
        state=state,
        intake=IntakeDetails(
            title=title,
            description=question or title,
            operational_question=question or title,
            area_or_region=region,
            required_output_format=output_format,
        ),
    )
