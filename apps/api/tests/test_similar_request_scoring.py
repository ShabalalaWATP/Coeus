from uuid import uuid4

from coeus.domain.enums import TicketState
from coeus.domain.tickets import IntakeDetails, TicketRecord
from coeus.services.rfi_ranking import lexical_score_for_product, lexical_text_score
from coeus.services.similar_request_scoring import score_similar_requests
from coeus.services.store_semantics import product_semantic_text
from store_projection_helpers import seed_product


class NoEmbeddingService:
    def embed(self, _text: str, *, purpose: str) -> None:
        return None


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

    assert score_similar_requests(source, (source, closed), NoEmbeddingService(), 0.0) == ()


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

    matches = score_similar_requests(source, (candidate,), NoEmbeddingService(), 0.0)

    assert matches[0].ticket_id == candidate.ticket_id
    assert matches[0].title == "Untitled requirement"
    assert "similarity:lexical-only" in matches[0].reasons
    assert "similarity:metadata-region" in matches[0].reasons
    assert "similarity:metadata-format" in matches[0].reasons


def test_no_match_tickets_are_still_open_similarity_candidates() -> None:
    source = _ticket("Gulf of Finland vessel activity")
    candidate = _ticket(
        "Gulf of Finland shipping activity",
        state=TicketState.RFI_NO_MATCH,
    )

    matches = score_similar_requests(source, (candidate,), NoEmbeddingService(), 0.0)

    assert matches[0].ticket_id == candidate.ticket_id
    assert matches[0].state == TicketState.RFI_NO_MATCH


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
