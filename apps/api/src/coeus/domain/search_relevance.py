from coeus.domain.store import StoreHybridCandidate

RRF_K = 60
LEXICAL_SCORE_FLOOR = 0.12
VECTOR_SIMILARITY_FLOOR = 0.18


def matched_tokens(
    query_tokens: tuple[str, ...],
    document_tokens: tuple[str, ...],
) -> tuple[str, ...]:
    document_forms = normalised_token_forms(document_tokens)
    return tuple(
        token for token in query_tokens if _token_forms(token).intersection(document_forms)
    )


def token_sets_overlap(left: tuple[str, ...], right: tuple[str, ...]) -> bool:
    right_forms = normalised_token_forms(right)
    return any(_token_forms(token).intersection(right_forms) for token in left)


def normalised_token_forms(tokens: tuple[str, ...]) -> frozenset[str]:
    """Expand conservative plural forms once for linear membership checks."""
    return frozenset(form for token in tokens for form in _token_forms(token))


def available_hybrid_legs(
    candidates: tuple[StoreHybridCandidate, ...],
    *,
    lexical_floor: float = LEXICAL_SCORE_FLOOR,
    vector_floor: float = VECTOR_SIMILARITY_FLOOR,
) -> int:
    lexical = any(_has_lexical_signal(candidate, lexical_floor) for candidate in candidates)
    vector = any(_has_vector_signal(candidate, vector_floor) for candidate in candidates)
    return max(1, int(lexical) + int(vector))


def hybrid_rrf_score(
    candidate: StoreHybridCandidate,
    available_legs: int,
    *,
    lexical_floor: float = LEXICAL_SCORE_FLOOR,
    vector_floor: float = VECTOR_SIMILARITY_FLOOR,
) -> float:
    raw = 0.0
    lexical_rank = candidate.lexical_rank
    vector_rank = candidate.vector_rank
    if lexical_rank is not None and candidate.lexical_score >= lexical_floor:
        raw += 1 / (RRF_K + lexical_rank)
    if vector_rank is not None and candidate.vector_score >= vector_floor:
        raw += 1 / (RRF_K + vector_rank)
    max_possible = available_legs / (RRF_K + 1)
    return raw / max_possible if max_possible else 0.0


def _has_lexical_signal(candidate: StoreHybridCandidate, lexical_floor: float) -> bool:
    return candidate.lexical_rank is not None and candidate.lexical_score >= lexical_floor


def _has_vector_signal(candidate: StoreHybridCandidate, vector_floor: float) -> bool:
    return candidate.vector_rank is not None and candidate.vector_score >= vector_floor


def _token_forms(token: str) -> frozenset[str]:
    forms = {token}
    for suffix in ("es", "s"):
        if not token.endswith(suffix):
            continue
        stem = token[: -len(suffix)]
        if len(stem) >= 3:
            forms.add(stem)
    return frozenset(forms)
