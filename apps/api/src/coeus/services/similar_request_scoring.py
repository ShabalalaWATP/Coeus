from dataclasses import dataclass
from math import sqrt
from re import findall
from uuid import UUID

from coeus.core.permissions import Permission
from coeus.domain.enums import TicketState
from coeus.domain.tickets import TicketRecord
from coeus.services.embeddings import EmbeddingService, cosine_similarity
from coeus.services.rfi_ranking import (
    LEXICAL_SCORE_FLOOR,
    RRF_K,
    STOP_WORDS,
    VECTOR_SIMILARITY_FLOOR,
    query_text,
)

CUSTOMER_SIMILARITY_THRESHOLD = 0.58
MANAGER_SIMILARITY_THRESHOLD = 0.50
MAX_SIMILAR_REQUESTS = 5
ROUTING_READ_PERMISSIONS = frozenset({Permission.RFA_REVIEW, Permission.COLLECTION_REVIEW})
OPEN_SIMILARITY_STATES = frozenset(
    {
        TicketState.RFI_SEARCHING,
        TicketState.RFI_MATCH_OFFERED,
        TicketState.RFI_NO_MATCH,
        TicketState.ROUTE_ASSESSMENT,
        TicketState.RFA_MANAGER_REVIEW,
        TicketState.CM_MANAGER_REVIEW,
        TicketState.ANALYST_ASSIGNMENT,
        TicketState.ANALYST_IN_PROGRESS,
        TicketState.QC_REVIEW,
        TicketState.REWORK_REQUIRED,
        TicketState.MANAGER_RELEASE,
    }
)


@dataclass(frozen=True)
class SimilarRequestMatch:
    ticket_id: UUID
    reference: str
    title: str
    state: TicketState
    score: float
    reasons: tuple[str, ...]
    already_linked: bool


def score_similar_requests(
    source: TicketRecord,
    candidates: tuple[TicketRecord, ...],
    embeddings: EmbeddingService,
    threshold: float,
) -> tuple[SimilarRequestMatch, ...]:
    """Score open tickets with RRF over lexical and embedding similarity.

    Source and candidate intake text are converted with `query_text`. Lexical
    rank uses normalised token overlap. Semantic rank uses cosine similarity
    between 384-dimension embeddings when available. Each available leg feeds
    Reciprocal Rank Fusion with k=60; the score is normalised to 0..1 and small
    metadata boosts are added for region and output-format overlap.
    """

    scoped = tuple(
        ticket
        for ticket in candidates
        if ticket.ticket_id != source.ticket_id and ticket.state in OPEN_SIMILARITY_STATES
    )
    if not scoped:
        return ()
    source_text = query_text(source.intake)
    query_embedding = embeddings.embed(source_text, purpose="similar-request-query")
    lexical_rank = _rank_lexical(source_text, scoped)
    vector_rank = _rank_vector(query_embedding, scoped, embeddings)
    available = max(1, int(bool(lexical_rank)) + int(bool(vector_rank)))
    matches = tuple(
        _match_for_candidate(
            source,
            candidate,
            lexical_rank.get(candidate.ticket_id),
            vector_rank.get(candidate.ticket_id),
            available,
        )
        for candidate in scoped
    )
    return tuple(
        sorted(
            (match for match in matches if match.score >= threshold),
            key=lambda item: (-item.score, item.title, item.reference),
        )[:MAX_SIMILAR_REQUESTS]
    )


def _rank_lexical(
    source_text: str, candidates: tuple[TicketRecord, ...]
) -> dict[UUID, tuple[int, float]]:
    source_tokens = _tokens(source_text)
    scored = [
        (_lexical_score(source_tokens, query_text(ticket.intake)), ticket) for ticket in candidates
    ]
    ranked = sorted(
        ((score, ticket) for score, ticket in scored if score >= LEXICAL_SCORE_FLOOR),
        key=lambda item: (-item[0], item[1].reference),
    )
    return {ticket.ticket_id: (index + 1, score) for index, (score, ticket) in enumerate(ranked)}


def _rank_vector(
    query_embedding: tuple[float, ...] | None,
    candidates: tuple[TicketRecord, ...],
    embeddings: EmbeddingService,
) -> dict[UUID, tuple[int, float]]:
    if query_embedding is None:
        return {}
    scored = []
    for ticket in candidates:
        vector = embeddings.embed(query_text(ticket.intake), purpose="similar-request-candidate")
        if vector is not None:
            scored.append((cosine_similarity(query_embedding, vector), ticket))
    ranked = sorted(
        ((score, ticket) for score, ticket in scored if score >= VECTOR_SIMILARITY_FLOOR),
        key=lambda item: (-item[0], item[1].reference),
    )
    return {ticket.ticket_id: (index + 1, score) for index, (score, ticket) in enumerate(ranked)}


def _match_for_candidate(
    source: TicketRecord,
    candidate: TicketRecord,
    lexical: tuple[int, float] | None,
    vector: tuple[int, float] | None,
    available_legs: int,
) -> SimilarRequestMatch:
    score = min(1.0, _rrf(lexical, vector, available_legs) + _metadata_boost(source, candidate))
    return SimilarRequestMatch(
        ticket_id=candidate.ticket_id,
        reference=candidate.reference,
        title=candidate.intake.title or "Untitled requirement",
        state=candidate.state,
        score=round(score, 4),
        reasons=_reasons(source, candidate, lexical, vector),
        already_linked=candidate.ticket_id in source.related_ticket_ids,
    )


def _rrf(
    lexical: tuple[int, float] | None, vector: tuple[int, float] | None, available_legs: int
) -> float:
    raw = 0.0
    if lexical is not None:
        raw += 1 / (RRF_K + lexical[0])
    if vector is not None:
        raw += 1 / (RRF_K + vector[0])
    return raw / (available_legs / (RRF_K + 1))


def _metadata_boost(source: TicketRecord, candidate: TicketRecord) -> float:
    score = 0.0
    if _has_overlap(source.intake.area_or_region, candidate.intake.area_or_region):
        score += 0.04
    if _has_overlap(source.intake.required_output_format, candidate.intake.required_output_format):
        score += 0.02
    return score


def _reasons(
    source: TicketRecord,
    candidate: TicketRecord,
    lexical: tuple[int, float] | None,
    vector: tuple[int, float] | None,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if lexical is not None:
        reasons.append(f"similarity:lexical-rank:{lexical[0]}")
    if vector is not None:
        reasons.append(f"similarity:vector:{vector[1]:.2f}")
    if lexical is not None and vector is None:
        reasons.append("similarity:lexical-only")
    if _has_overlap(source.intake.area_or_region, candidate.intake.area_or_region):
        reasons.append("similarity:metadata-region")
    if _has_overlap(source.intake.required_output_format, candidate.intake.required_output_format):
        reasons.append("similarity:metadata-format")
    return tuple(reasons)


def _lexical_score(source_tokens: tuple[str, ...], candidate_text: str) -> float:
    candidate_tokens = set(_tokens(candidate_text))
    if not source_tokens or not candidate_tokens:
        return 0.0
    overlap = sum(1 for token in source_tokens if token in candidate_tokens)
    return overlap / sqrt(len(source_tokens) * len(candidate_tokens))


def _has_overlap(left: str | None, right: str | None) -> bool:
    return bool(left and right and set(_tokens(left)).intersection(_tokens(right)))


def _tokens(text: str) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            token
            for token in findall(r"[a-z0-9]+", text.casefold())
            if len(token) >= 2 and token not in STOP_WORDS
        )
    )
