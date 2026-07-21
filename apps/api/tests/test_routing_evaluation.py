from dataclasses import replace
from datetime import UTC, datetime, timedelta

from coeus.domain.jioc_routing import ROUTING_RELEASE, RoutingOperationalSnapshot
from coeus.services.capability_catalogue import CapabilityCatalogue
from coeus.services.jioc_routing_context import build_routing_context
from coeus.services.jioc_routing_policy import decide
from coeus.services.routing_agents import CmCapabilityAgent, RfaCapabilityAgent
from coeus.services.routing_evaluation import (
    RoutingEvaluationCase,
    RoutingEvaluationResult,
    evaluate_routing_release,
)
from test_jioc_routing_safety import _ticket


def test_versioned_labelled_evaluation_is_an_active_release_gate() -> None:
    report = evaluate_routing_release(_classify)

    assert report.release == ROUTING_RELEASE
    assert report.total >= 16
    assert report.correct == report.total
    assert report.unsafe_automatic_routes == 0
    assert report.rfa_false_positives == report.rfa_false_negatives == 0
    assert report.cm_false_positives == report.cm_false_negatives == 0
    assert report.conflict_accuracy == 1.0
    assert report.expected_abstentions == report.actual_abstentions
    assert report.abstention_rate > 0.5
    assert report.active_ready is True


def test_evaluation_gate_rejects_unsafe_route_bias() -> None:
    report = evaluate_routing_release(
        lambda _case: RoutingEvaluationResult(
            "auto_applied",
            "rfa",
            ("existing_information_assessment",),
        )
    )

    assert report.active_ready is False
    assert report.unsafe_automatic_routes > 0
    assert report.rfa_false_positives > 0
    assert report.cm_false_negatives > 0
    assert report.conflict_accuracy == 0.0
    assert report.actual_abstentions == 0


def _classify(case: RoutingEvaluationCase) -> RoutingEvaluationResult:
    now = datetime(2026, 7, 20, 12, tzinfo=UTC)
    ticket = _ticket(
        case.description,
        case.output_format,
        now,
        priority=case.priority,
        deadline=case.deadline,
        restrictions=case.restrictions,
        product_offer_unresolved=case.product_offer_unresolved,
        active_work_completed=case.active_work_completed,
        active_work_offer_unresolved=case.active_work_offer_unresolved,
    )
    catalogue = CapabilityCatalogue()
    rfa = RfaCapabilityAgent(catalogue).review(ticket)
    cm = CmCapabilityAgent(catalogue).review(ticket)
    candidate_ids = tuple(
        dict.fromkeys(
            item
            for item in (
                rfa.suggested_team_id,
                cm.suggested_collection_team_id,
                *(candidate.team_id for candidate in rfa.candidate_teams),
                *(candidate.team_id for candidate in cm.candidate_teams),
            )
            if item
        )
    )
    snapshot = RoutingOperationalSnapshot(
        "capability-catalogue-v1",
        now - timedelta(seconds=case.snapshot_age_seconds) if case.snapshot_present else None,
        tuple(f"{team_id}:{case.capacity}:1" for team_id in candidate_ids),
    )
    context = build_routing_context(ticket, snapshot, now)
    if not case.search_ready:
        context = replace(context, search_assurance="assisted", search_coverage="partial")
    disposition, route, _strength, codes, _questions = decide(ticket, context, rfa, cm)
    return RoutingEvaluationResult(disposition, route.value, codes)
