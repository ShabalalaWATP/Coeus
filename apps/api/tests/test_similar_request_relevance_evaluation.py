import json
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import cast
from uuid import uuid4

from coeus.domain.tickets import AnalystAssignment, RoutingRoute
from coeus.services.embeddings import EmbeddingService
from coeus.services.search_evaluation import SearchEvaluationRun, evaluate_search_runs
from coeus.services.similar_request_scoring import (
    MANAGER_SIMILARITY_THRESHOLD,
    score_similar_requests,
)
from test_similar_request_scoring import _ticket

DATA = Path(__file__).parent / "relevance"


def test_route_aware_similar_request_qrels_pass_release_gates() -> None:
    corpus = _jsonl(DATA / "request_corpus.v1.jsonl")
    cases = _jsonl(DATA / "similar_request_qrels.v1.jsonl")
    requests = {str(row["request_id"]): _request(row) for row in corpus}
    request_clusters = {str(row["request_id"]): row["cluster"] for row in corpus}

    runs = tuple(_run(case, requests, request_clusters) for case in cases)
    report = evaluate_search_runs(runs)

    assert report.access_leakage_count == 0
    assert report.recall_at_5 == 1
    assert report.precision_at_5 == 1
    assert report.ndcg_at_5 >= 0.90
    assert report.false_definitive_no_match_rate == 0
    assert report.false_offer_rate == 0
    assert report.degraded_mode_identification == 1
    assert report.passes_release_gates is True


def _run(case, requests, request_clusters) -> SearchEvaluationRun:
    hidden = frozenset(case["hidden"])
    visible = {key: value for key, value in requests.items() if key not in hidden}
    source_fields = case["source"]
    source = _ticket(
        source_fields["title"],
        question=source_fields["question"],
        region=source_fields["region"],
    )
    cluster = case["cluster"]
    semantic_ids = sorted(
        key for key in visible if cluster is not None and request_clusters[key] == cluster
    )
    semantic = {visible[key].ticket_id: (index + 1, 0.92) for index, key in enumerate(semantic_ids)}
    matches = score_similar_requests(
        source,
        tuple(visible.values()),
        cast(EmbeddingService, object()),
        MANAGER_SIMILARITY_THRESHOLD,
        semantic_rank_override=semantic,
    )
    reverse_ids = {value.ticket_id: key for key, value in visible.items()}
    return SearchEvaluationRun(
        query_id=case["query_id"],
        ranked_ids=tuple(reverse_ids[match.ticket_id] for match in matches),
        relevance={key: int(value) for key, value in case["relevance"].items()},
        visible_ids=frozenset(visible),
        retrieval_mode="hybrid" if cluster is not None else "lexical_only",
        expected_mode=case["expected_mode"],
        expect_no_match=case["expect_no_match"],
    )


def _request(row):
    ticket = _ticket(row["title"], question=row["question"], region=row["region"])
    route = row["route"]
    if route == "RFI":
        return ticket
    assignment = AnalystAssignment(
        assignment_id=uuid4(),
        ticket_id=ticket.ticket_id,
        analyst_user_id=uuid4(),
        assigned_by_user_id=uuid4(),
        route=RoutingRoute[route],
        created_at=datetime.now(UTC),
        team_name=f"Synthetic {route} team",
    )
    return replace(ticket, analyst_assignments=(assignment,))


def _jsonl(path: Path):
    rows = tuple(json.loads(line) for line in path.read_text(encoding="utf-8").splitlines())
    assert rows and all(row["version"] == 1 for row in rows)
    return rows
