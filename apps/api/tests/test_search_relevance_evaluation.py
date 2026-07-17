import json
from dataclasses import replace
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

import pytest

from coeus.domain.store import StoreHybridCandidate
from coeus.domain.tickets import IntakeDetails
from coeus.services.rfi_ranking import (
    LEXICAL_SCORE_FLOOR,
    lexical_score_for_product,
    rank_hybrid_rfi_candidates,
)
from coeus.services.search_evaluation import SearchEvaluationRun, evaluate_search_runs
from store_projection_helpers import seed_product

DATA = Path(__file__).parent / "relevance"


def test_versioned_synthetic_product_relevance_set_passes_release_gates() -> None:
    corpus_rows = _jsonl(DATA / "product_corpus.v1.jsonl")
    qrels = _jsonl(DATA / "product_search_qrels.v1.jsonl")
    products = {row["product_id"]: _product(row) for row in corpus_rows}
    reverse_ids = {str(product.product_id): key for key, product in products.items()}

    runs = tuple(_run_case(case, products, reverse_ids) for case in qrels)
    report = evaluate_search_runs(runs)

    assert report.query_count == 10
    assert report.access_leakage_count == 0
    assert report.recall_at_5 >= 0.90
    assert report.precision_at_5 >= 0.70
    assert report.ndcg_at_5 >= 0.85
    assert report.no_match_false_offer_rate <= 0.10
    assert report.degraded_mode_identification == 1.0
    assert report.passes_release_gates is True


def test_evaluation_report_detects_leakage_bad_ranking_and_wrong_mode() -> None:
    report = evaluate_search_runs(
        (
            SearchEvaluationRun(
                query_id="bad",
                ranked_ids=("hidden", "wrong"),
                relevance={"right": 3},
                visible_ids=frozenset({"right", "wrong"}),
                retrieval_mode="hybrid",
                expected_mode="lexical_only",
            ),
            SearchEvaluationRun(
                query_id="bad-no-match",
                ranked_ids=("wrong",),
                relevance={},
                visible_ids=frozenset({"wrong"}),
                retrieval_mode="lexical_only",
                expected_mode="lexical_only",
                expect_no_match=True,
            ),
        )
    )

    assert report.access_leakage_count == 1
    assert report.recall_at_5 == 0
    assert report.precision_at_5 == 0
    assert report.ndcg_at_5 == 0
    assert report.no_match_false_offer_rate == 1
    assert report.degraded_mode_identification == 0.5
    assert report.passes_release_gates is False


def test_evaluation_rejects_non_positive_cutoff() -> None:
    with pytest.raises(ValueError, match="positive"):
        evaluate_search_runs((), limit=0)


def _run_case(
    case: dict[str, object],
    products: dict[str, object],
    reverse_ids: dict[str, str],
) -> SearchEvaluationRun:
    hidden = frozenset(str(item) for item in case["hidden"])
    visible = {key: value for key, value in products.items() if key not in hidden}
    intake = IntakeDetails(**case["intake"])
    lexical_scores = {
        key: lexical_score_for_product(product, " ".join(_intake_values(intake)))
        for key, product in visible.items()
    }
    lexical_order = sorted(
        (key for key, score in lexical_scores.items() if score >= LEXICAL_SCORE_FLOOR),
        key=lambda key: (-lexical_scores[key], key),
    )
    lexical_ranks = {key: index + 1 for index, key in enumerate(lexical_order)}
    cluster = case["cluster"]
    vector_order = sorted(
        key for key in visible if cluster is not None and _corpus_row(key)["cluster"] == cluster
    )
    vector_ranks = {key: index + 1 for index, key in enumerate(vector_order)}
    candidate_ids = set(lexical_ranks) | set(vector_ranks)
    candidates = tuple(
        StoreHybridCandidate(
            product=visible[key],
            lexical_rank=lexical_ranks.get(key),
            lexical_score=lexical_scores[key],
            vector_rank=vector_ranks.get(key),
            vector_score=0.92 if key in vector_ranks else 0.0,
            lexical_only=key not in vector_ranks,
        )
        for key in sorted(candidate_ids)
    )
    offers = rank_hybrid_rfi_candidates(candidates, intake)
    return SearchEvaluationRun(
        query_id=str(case["query_id"]),
        ranked_ids=tuple(reverse_ids[str(offer.product_id)] for offer in offers),
        relevance={str(key): int(value) for key, value in case["relevance"].items()},
        visible_ids=frozenset(visible),
        retrieval_mode="hybrid" if cluster is not None else "lexical_only",
        expected_mode=str(case["expected_mode"]),
        expect_no_match=bool(case["expect_no_match"]),
    )


def _product(row: dict[str, object]):
    product = seed_product()
    return replace(
        product,
        product_id=uuid5(NAMESPACE_URL, str(row["product_id"])),
        metadata=replace(
            product.metadata,
            title=str(row["title"]),
            summary=str(row["summary"]),
            description=str(row["description"]),
            area_or_region=str(row["region"]),
            time_period_start=str(row["time_start"]),
            time_period_end=str(row["time_end"]),
            semantic_labels=frozenset(),
        ),
    )


def _jsonl(path: Path) -> tuple[dict[str, object], ...]:
    rows = tuple(json.loads(line) for line in path.read_text(encoding="utf-8").splitlines())
    assert rows and all(row["version"] == 1 for row in rows)
    return rows


def _corpus_row(product_id: str) -> dict[str, object]:
    return next(
        row for row in _jsonl(DATA / "product_corpus.v1.jsonl") if row["product_id"] == product_id
    )


def _intake_values(intake: IntakeDetails) -> tuple[str, ...]:
    return tuple(str(value) for value in vars(intake).values() if value)
