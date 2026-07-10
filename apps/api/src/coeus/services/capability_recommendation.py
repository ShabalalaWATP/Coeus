"""Scored team recommendation over the capability catalogue.

Replaces plain keyword counting with a transparent weighted score:
relevance (keywords + requested disciplines) 0.4, region coverage 0.3, team
rank 0.2 and priority fit 0.1. Every candidate carries prefixed reason tags in
the same idiom as the search and prioritisation scorers, so a manager can see
exactly why a team was suggested. Teams with no keyword or discipline signal
are never recommended.
"""

from coeus.domain.capabilities import CandidateTeam, CapabilityTeam

WEIGHT_RELEVANCE = 0.4
WEIGHT_REGION = 0.3
WEIGHT_RANK = 0.2
WEIGHT_PRIORITY_FIT = 0.1

RECOMMENDATION_LIMIT = 3
HIGH_PRIORITY_TIERS = frozenset({"P1", "P2"})


def recommend_teams(
    teams: tuple[CapabilityTeam, ...],
    *,
    terms: frozenset[str],
    disciplines: frozenset[str] = frozenset(),
    region: str | None = None,
    priority_tier: str | None = None,
    limit: int = RECOMMENDATION_LIMIT,
) -> tuple[CandidateTeam, ...]:
    requested = frozenset(item.casefold() for item in disciplines)
    scored: list[tuple[float, str, CandidateTeam]] = []
    for team in teams:
        overlap = team.keywords.intersection(terms)
        matched = frozenset(item.casefold() for item in team.disciplines).intersection(requested)
        if not overlap and not matched:
            continue
        relevance = _relevance(overlap, matched, requested)
        region_score, region_reason = _region_fit(team, region)
        fit_score, fit_reason = _priority_fit(team, priority_tier)
        score = round(
            WEIGHT_RELEVANCE * relevance
            + WEIGHT_REGION * region_score
            + WEIGHT_RANK * team.rank
            + WEIGHT_PRIORITY_FIT * fit_score,
            4,
        )
        reasons = (
            *(f"capability:keyword:{keyword}" for keyword in sorted(overlap)[:3]),
            *(f"capability:discipline:{item}" for item in sorted(matched)),
            region_reason,
            f"capability:rank:{team.rank}",
            fit_reason,
        )
        candidate = CandidateTeam(
            team_id=team.team_id, name=team.name, score=score, reasons=reasons
        )
        scored.append((score, team.name, candidate))
    ranked = sorted(scored, key=lambda item: (-item[0], item[1]))
    return tuple(candidate for _score, _name, candidate in ranked[:limit])


def _relevance(
    overlap: frozenset[str], matched: frozenset[str], requested: frozenset[str]
) -> float:
    keyword_score = min(1.0, len(overlap) / 3)
    # No stated discipline preference scores neutral rather than penalising.
    discipline_score = (1.0 if matched else 0.0) if requested else 0.5
    return min(1.0, 0.6 * keyword_score + 0.4 * discipline_score)


def _region_fit(team: CapabilityTeam, region: str | None) -> tuple[float, str]:
    stated = (region or "").casefold().strip()
    if not stated:
        return 0.5, "capability:region:unspecified"
    for label in sorted(team.regions):
        if label != "global" and (label in stated or stated in label):
            return 1.0, f"capability:region:{label.replace(' ', '-')}"
    if "global" in team.regions:
        return 0.6, "capability:region:global"
    return 0.2, "capability:region:unmatched"


def _priority_fit(team: CapabilityTeam, priority_tier: str | None) -> tuple[float, str]:
    if priority_tier in HIGH_PRIORITY_TIERS:
        # Urgent work leans towards the heavyweight teams.
        return team.rank, f"capability:priority-fit:{priority_tier.casefold()}"
    return 0.5, "capability:priority-fit:standard"
