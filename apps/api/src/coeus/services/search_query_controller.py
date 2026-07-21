"""Deterministic controller for admitting advisory search wording."""

import unicodedata
from dataclasses import dataclass

from coeus.services.search_planner import SearchPlannerAdvice

MAX_EFFECTIVE_QUERY_BYTES = 32_768


@dataclass(frozen=True)
class SearchQueryHint:
    """One normalised planner hint admitted into the effective query."""

    kind: str
    value: str


@dataclass(frozen=True)
class ControlledSearchQuery:
    """A base-preserving search query and its deterministic admission record."""

    text: str
    included_hints: tuple[SearchQueryHint, ...]
    advice_truncated: bool


def control_search_query(
    base_query: str,
    advice: SearchPlannerAdvice,
    *,
    max_total_bytes: int = MAX_EFFECTIVE_QUERY_BYTES,
) -> ControlledSearchQuery:
    """Append unique, normalised hints without changing or truncating the base query."""
    if max_total_bytes < 0 or len(base_query.encode("utf-8")) > max_total_bytes:
        raise ValueError("the complete base query exceeds the effective-query byte limit")
    candidates = _normalised_hints(advice)
    if not base_query or not candidates:
        return ControlledSearchQuery(base_query, (), bool(candidates and not base_query))

    text = base_query
    included: list[SearchQueryHint] = []
    truncated = False
    for hint in candidates:
        suffix = f"\n{_label(hint.kind)}: {hint.value}"
        if len((text + suffix).encode("utf-8")) > max_total_bytes:
            truncated = True
            continue
        text += suffix
        included.append(hint)
    return ControlledSearchQuery(text, tuple(included), truncated)


def _normalised_hints(advice: SearchPlannerAdvice) -> tuple[SearchQueryHint, ...]:
    groups = (
        ("expansion", advice.query_expansions),
        ("entity", advice.entities),
        ("date-text-hint", advice.date_interpretations),
        ("alternative-term", advice.alternative_terminology),
    )
    hints: list[SearchQueryHint] = []
    seen: set[str] = set()
    for kind, values in groups:
        for value in values:
            normalised = " ".join(unicodedata.normalize("NFKC", value).split())
            key = normalised.casefold()
            if not normalised or key in seen or _has_control_character(normalised):
                continue
            seen.add(key)
            hints.append(SearchQueryHint(kind, normalised))
    return tuple(hints)


def _has_control_character(value: str) -> bool:
    return any(unicodedata.category(character).startswith("C") for character in value)


def _label(kind: str) -> str:
    return {
        "expansion": "Query expansion",
        "entity": "Entity",
        "date-text-hint": "Date interpretation (text only)",
        "alternative-term": "Alternative terminology",
    }[kind]
