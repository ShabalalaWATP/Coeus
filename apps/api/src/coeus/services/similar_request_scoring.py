from collections.abc import Callable
from dataclasses import dataclass
from typing import cast
from uuid import UUID

from coeus.core.permissions import Permission
from coeus.domain.enums import TicketState
from coeus.domain.tickets import RoutingRoute, TicketRecord
from coeus.services.embeddings import EmbeddingService, cosine_similarity
from coeus.services.rfi_ranking import (
    LEXICAL_SCORE_FLOOR,
    RRF_K,
    VECTOR_SIMILARITY_FLOOR,
    lexical_text_score,
    query_text,
    token_overlap,
)

CUSTOMER_SIMILARITY_THRESHOLD = 0.58
MANAGER_SIMILARITY_THRESHOLD = 0.50
MAX_SIMILAR_REQUESTS = 5
MAX_VECTOR_CANDIDATES = 32
ROUTING_READ_PERMISSIONS = frozenset(
    {Permission.JIOC_REVIEW, Permission.RFA_REVIEW, Permission.COLLECTION_REVIEW}
)
OPEN_SIMILARITY_STATES = frozenset(
    {
        TicketState.INFO_REQUIRED,
        TicketState.RFI_SEARCHING,
        TicketState.RFI_MATCH_OFFERED,
        TicketState.RFI_NO_MATCH,
        TicketState.JIOC_REVIEW,
        TicketState.COLLECT_CHOICE,
        TicketState.ANALYST_ASSIGNMENT,
        TicketState.ANALYST_IN_PROGRESS,
        TicketState.MANAGER_APPROVAL,
        TicketState.QC_REVIEW,
        TicketState.REWORK_REQUIRED,
        TicketState.DISSEMINATION_READY,
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
    already_marked_duplicate: bool
    request_kind: str
    approved_route: str | None
    assigned_team: str | None
    requesting_unit: str | None
    supported_operation: str | None
    time_period_start: str | None
    time_period_end: str | None


def score_similar_requests(
    source: TicketRecord,
    candidates: tuple[TicketRecord, ...],
    embeddings: EmbeddingService,
    threshold: float,
    principal_id: UUID | None = None,
    semantic_rank_override: dict[UUID, tuple[int, float]] | None = None,
) -> tuple[SimilarRequestMatch, ...]:
    """Score open tickets with RRF over lexical and embedding similarity.

    Source and candidate intake text are converted with `query_text`. Lexical
    rank uses normalised token overlap. Semantic rank uses the generation-aware
    search index when supplied. The legacy embedding service remains a safe
    fallback until a v2 re-index is ready. Each available leg feeds Reciprocal
    Rank Fusion with k=60; the score is normalised to 0..1 and small metadata
    boosts are added for region and output-format overlap.
    """

    scoped = tuple(
        ticket
        for ticket in candidates
        if ticket.ticket_id != source.ticket_id and ticket.state in OPEN_SIMILARITY_STATES
    )
    if not scoped:
        return ()
    source_text = query_text(source.intake)
    embedding_principal = principal_id or source.requester_user_id
    lexical_rank = _rank_lexical(source_text, scoped)
    if semantic_rank_override is None:
        query_embedding = _embed_cached(
            embeddings,
            source_text,
            purpose="similar-request-query",
            principal_id=embedding_principal,
        )
        vector_candidates = _vector_candidates(source_text, scoped)
        vector_rank = _rank_vector(
            query_embedding,
            vector_candidates,
            embeddings,
            embedding_principal,
        )
    else:
        scoped_ids = {ticket.ticket_id for ticket in scoped}
        vector_rank = {
            ticket_id: value
            for ticket_id, value in semantic_rank_override.items()
            if ticket_id in scoped_ids
        }
    matches = tuple(
        _match_with_available_legs(source, candidate, lexical_rank, vector_rank)
        for candidate in scoped
    )
    return tuple(
        sorted(
            (match for match in matches if match.score >= threshold),
            key=lambda item: (-item.score, item.title, item.reference),
        )[:MAX_SIMILAR_REQUESTS]
    )


def _match_with_available_legs(
    source: TicketRecord,
    candidate: TicketRecord,
    lexical_rank: dict[UUID, tuple[int, float]],
    vector_rank: dict[UUID, tuple[int, float]],
) -> SimilarRequestMatch:
    lexical = lexical_rank.get(candidate.ticket_id)
    vector = vector_rank.get(candidate.ticket_id)
    available = max(1, int(lexical is not None) + int(vector is not None))
    return _match_for_candidate(source, candidate, lexical, vector, available)


def _rank_lexical(
    source_text: str, candidates: tuple[TicketRecord, ...]
) -> dict[UUID, tuple[int, float]]:
    scored = [
        (lexical_text_score(source_text, query_text(ticket.intake)), ticket)
        for ticket in candidates
    ]
    ranked = sorted(
        ((score, ticket) for score, ticket in scored if score >= LEXICAL_SCORE_FLOOR),
        key=lambda item: (-item[0], item[1].reference),
    )
    return {ticket.ticket_id: (index + 1, score) for index, (score, ticket) in enumerate(ranked)}


def _vector_candidates(
    source_text: str, candidates: tuple[TicketRecord, ...]
) -> tuple[TicketRecord, ...]:
    """Bound semantic work using a deterministic lexical pre-rank."""
    ranked = sorted(
        candidates,
        key=lambda ticket: (
            -lexical_text_score(source_text, query_text(ticket.intake)),
            ticket.reference,
        ),
    )
    return tuple(ranked[:MAX_VECTOR_CANDIDATES])


def _rank_vector(
    query_embedding: tuple[float, ...] | None,
    candidates: tuple[TicketRecord, ...],
    embeddings: EmbeddingService,
    principal_id: UUID,
) -> dict[UUID, tuple[int, float]]:
    if query_embedding is None:
        return {}
    scored = []
    for ticket in candidates:
        vector = _embed_cached(
            embeddings,
            query_text(ticket.intake),
            purpose="similar-request-candidate",
            principal_id=principal_id,
        )
        if vector is not None:
            scored.append((cosine_similarity(query_embedding, vector), ticket))
    ranked = sorted(
        ((score, ticket) for score, ticket in scored if score >= VECTOR_SIMILARITY_FLOOR),
        key=lambda item: (-item[0], item[1].reference),
    )
    return {ticket.ticket_id: (index + 1, score) for index, (score, ticket) in enumerate(ranked)}


def _embed_cached(
    embeddings: EmbeddingService, text: str, *, purpose: str, principal_id: UUID
) -> tuple[float, ...] | None:
    """Use the hardened cache while retaining compatibility with narrow test adapters."""
    cached = getattr(embeddings, "embed_cached", None)
    if callable(cached):
        cached_call = cast(
            Callable[..., tuple[float, ...] | None],
            cached,
        )
        return cached_call(text, purpose=purpose, principal_id=principal_id)
    return embeddings.embed(text, purpose=purpose, principal_id=principal_id)


def _match_for_candidate(
    source: TicketRecord,
    candidate: TicketRecord,
    lexical: tuple[int, float] | None,
    vector: tuple[int, float] | None,
    available_legs: int,
) -> SimilarRequestMatch:
    score = min(1.0, _rrf(lexical, vector, available_legs) + _metadata_boost(source, candidate))
    route = _approved_route(candidate)
    return SimilarRequestMatch(
        ticket_id=candidate.ticket_id,
        reference=candidate.reference,
        title=candidate.intake.title or "Untitled requirement",
        state=candidate.state,
        score=round(score, 4),
        reasons=_reasons(source, candidate, lexical, vector),
        already_linked=candidate.ticket_id in source.related_ticket_ids,
        already_marked_duplicate=source.duplicate_of_ticket_id == candidate.ticket_id,
        request_kind=_request_kind(route),
        approved_route=route.value if route else None,
        assigned_team=_assigned_team(candidate),
        requesting_unit=candidate.intake.requesting_unit,
        supported_operation=candidate.intake.supported_operation,
        time_period_start=candidate.intake.time_period_start,
        time_period_end=candidate.intake.time_period_end,
    )


def _rrf(
    lexical: tuple[int, float] | None, vector: tuple[int, float] | None, available_legs: int
) -> float:
    rank_signal = 0.0
    absolute_signal = 0.0
    leg_scores: list[float] = []
    if lexical is not None:
        lexical_rank_signal = 1 / (RRF_K + lexical[0])
        rank_signal += lexical_rank_signal
        absolute_signal += lexical[1]
        leg_scores.append((0.15 * lexical_rank_signal * (RRF_K + 1)) + (0.85 * lexical[1]))
    if vector is not None:
        vector_rank_signal = 1 / (RRF_K + vector[0])
        vector_absolute_signal = max(
            0.0,
            (vector[1] - VECTOR_SIMILARITY_FLOOR) / (1.0 - VECTOR_SIMILARITY_FLOOR),
        )
        rank_signal += vector_rank_signal
        absolute_signal += vector_absolute_signal
        leg_scores.append(
            (0.15 * vector_rank_signal * (RRF_K + 1)) + (0.85 * vector_absolute_signal)
        )
    normalised_rank = rank_signal / (available_legs / (RRF_K + 1))
    normalised_absolute = absolute_signal / available_legs
    fused = (0.15 * normalised_rank) + (0.85 * normalised_absolute)
    return max((fused, *leg_scores), default=0.0)


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


def _has_overlap(left: str | None, right: str | None) -> bool:
    return bool(left and right and token_overlap(left, right))


def _approved_route(ticket: TicketRecord) -> RoutingRoute | None:
    approved = next(
        (
            decision.route
            for decision in reversed(ticket.manager_decisions)
            if decision.status.value == "approved"
        ),
        None,
    )
    if approved:
        return approved
    if ticket.analyst_assignments:
        return ticket.analyst_assignments[-1].route
    if ticket.route_recommendations:
        return ticket.route_recommendations[-1].recommended_route
    return None


def _request_kind(route: RoutingRoute | None) -> str:
    if route == RoutingRoute.RFA:
        return "RFA"
    if route == RoutingRoute.CM:
        return "Collection"
    return "RFI"


def _assigned_team(ticket: TicketRecord) -> str | None:
    assignment = next(
        (item for item in reversed(ticket.analyst_assignments) if item.active),
        None,
    )
    return assignment.team_name if assignment else None
