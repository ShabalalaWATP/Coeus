"""Release-gate metrics for labelled synthetic search evaluations."""

from dataclasses import dataclass
from math import log2

RECALL_AT_5_GATE = 0.95
PRECISION_AT_5_GATE = 0.95
NDCG_AT_5_GATE = 0.90
FALSE_DEFINITIVE_NO_MATCH_GATE = 0.01
FALSE_OFFER_GATE = 0.02
DEGRADED_IDENTIFICATION_GATE = 1.0
CITATION_IDENTITY_GATE = 1.0
PASSAGE_SUPPORT_GATE = 0.95


@dataclass(frozen=True)
class SearchEvaluationRun:
    query_id: str
    ranked_ids: tuple[str, ...]
    relevance: dict[str, int]
    visible_ids: frozenset[str]
    retrieval_mode: str
    expected_mode: str
    expect_no_match: bool = False
    reported_outcome: str | None = None
    reported_assurance: str = "definitive"
    temporal_constraints_satisfied: bool = True
    citation_identity_correct: bool = True
    passage_support: float = 1.0


@dataclass(frozen=True)
class SearchEvaluationReport:
    query_count: int
    access_leakage_count: int
    recall_at_5: float
    precision_at_5: float
    ndcg_at_5: float
    false_definitive_no_match_rate: float
    false_offer_rate: float
    degraded_mode_identification: float
    temporal_constraint_violations: int
    citation_identity_rate: float
    passage_support_rate: float

    @property
    def no_match_false_offer_rate(self) -> float:
        """Compatibility name used by the earlier evaluation report."""
        return self.false_offer_rate

    @property
    def passes_release_gates(self) -> bool:
        return (
            self.access_leakage_count == 0
            and self.recall_at_5 >= RECALL_AT_5_GATE
            and self.precision_at_5 >= PRECISION_AT_5_GATE
            and self.ndcg_at_5 >= NDCG_AT_5_GATE
            and self.false_definitive_no_match_rate <= FALSE_DEFINITIVE_NO_MATCH_GATE
            and self.false_offer_rate <= FALSE_OFFER_GATE
            and self.degraded_mode_identification >= DEGRADED_IDENTIFICATION_GATE
            and self.temporal_constraint_violations == 0
            and self.citation_identity_rate >= CITATION_IDENTITY_GATE
            and self.passage_support_rate >= PASSAGE_SUPPORT_GATE
        )


def evaluate_search_runs(
    runs: tuple[SearchEvaluationRun, ...], *, limit: int = 5
) -> SearchEvaluationReport:
    if limit < 1:
        raise ValueError("Search evaluation limit must be positive.")
    positive = tuple(run for run in runs if any(grade > 0 for grade in run.relevance.values()))
    no_match = tuple(run for run in runs if run.expect_no_match)
    degraded = tuple(run for run in runs if run.expected_mode != "hybrid")
    offered = tuple(run for run in runs if run.ranked_ids[:limit])
    leakage = sum(
        ranked_id not in run.visible_ids for run in runs for ranked_id in run.ranked_ids[:limit]
    )
    return SearchEvaluationReport(
        query_count=len(runs),
        access_leakage_count=leakage,
        recall_at_5=_mean(tuple(_recall(run, limit) for run in positive)),
        precision_at_5=_mean(tuple(_precision(run, limit) for run in positive)),
        ndcg_at_5=_mean(tuple(_ndcg(run, limit) for run in positive)),
        false_definitive_no_match_rate=_mean(
            tuple(
                float(
                    _reported_outcome(run) == "no_match" and run.reported_assurance == "definitive"
                )
                for run in positive
            )
        ),
        false_offer_rate=_mean(tuple(float(bool(run.ranked_ids[:limit])) for run in no_match)),
        degraded_mode_identification=_mean(
            tuple(float(run.retrieval_mode == run.expected_mode) for run in degraded),
            empty=1.0,
        ),
        temporal_constraint_violations=sum(not run.temporal_constraints_satisfied for run in runs),
        citation_identity_rate=_mean(
            tuple(float(run.citation_identity_correct) for run in offered), empty=1.0
        ),
        passage_support_rate=_mean(tuple(run.passage_support for run in offered), empty=1.0),
    )


def _reported_outcome(run: SearchEvaluationRun) -> str:
    return run.reported_outcome or ("offers" if run.ranked_ids else "no_match")


def _recall(run: SearchEvaluationRun, limit: int) -> float:
    relevant = {item for item, grade in run.relevance.items() if grade > 0}
    return len(relevant.intersection(run.ranked_ids[:limit])) / len(relevant)


def _precision(run: SearchEvaluationRun, limit: int) -> float:
    retrieved = run.ranked_ids[:limit]
    if not retrieved:
        return 0.0
    relevant = {item for item, grade in run.relevance.items() if grade > 0}
    return len(relevant.intersection(retrieved)) / len(retrieved)


def _ndcg(run: SearchEvaluationRun, limit: int) -> float:
    actual = _dcg(tuple(run.relevance.get(item, 0) for item in run.ranked_ids[:limit]))
    ideal = _dcg(tuple(sorted(run.relevance.values(), reverse=True)[:limit]))
    return actual / ideal if ideal else 1.0


def _dcg(grades: tuple[int, ...]) -> float:
    return float(sum((2**grade - 1) / log2(index + 2) for index, grade in enumerate(grades)))


def _mean(values: tuple[float, ...], *, empty: float = 0.0) -> float:
    return sum(values) / len(values) if values else empty
