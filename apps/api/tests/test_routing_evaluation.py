from dataclasses import replace
from datetime import UTC, datetime, timedelta

from coeus.core.config import Settings
from coeus.domain.jioc_routing import (
    ROUTING_RELATIONAL_CAPACITY_EVALUATION_VERSION,
    ROUTING_RELATIONAL_CAPACITY_RELEASE,
    ROUTING_RELEASE,
    RoutingOperationalSnapshot,
)
from coeus.services.capability_catalogue import CapabilityCatalogue
from coeus.services.jioc_routing_context import build_routing_context
from coeus.services.jioc_routing_policy import decide
from coeus.services.routing_agents import CmCapabilityAgent, RfaCapabilityAgent
from coeus.services.routing_demand_range import (
    RELATIONAL_DELIVERY_LEAVES,
    RoutingDemandRange,
    routing_capacity_status,
)
from coeus.services.routing_evaluation import (
    BASE_ROUTING_CASES,
    REPLAY_ROUTING_CASES,
    RoutingEvaluationCase,
    RoutingEvaluationResult,
    evaluate_routing_release,
)
from test_jioc_routing_safety import _ticket


def test_versioned_labelled_evaluation_passes_metrics_but_requires_its_own_approval() -> None:
    report = evaluate_routing_release(_classify)

    assert report.evaluation_version == ROUTING_RELATIONAL_CAPACITY_EVALUATION_VERSION
    assert report.release == ROUTING_RELATIONAL_CAPACITY_RELEASE
    assert report.release != ROUTING_RELEASE
    assert report.total == 48
    assert report.correct == report.total
    assert report.unsafe_automatic_routes == 0
    assert report.rfa_false_positives == report.rfa_false_negatives == 0
    assert report.cm_false_positives == report.cm_false_negatives == 0
    assert report.conflict_accuracy == 1.0
    assert report.replay_mismatches == 0
    assert report.expected_abstentions == report.actual_abstentions
    assert report.abstention_rate > 0.5
    assert report.delivery_leaves_covered == RELATIONAL_DELIVERY_LEAVES
    assert report.release_approved is False
    assert report.active_ready is False


def test_relational_evaluation_cannot_inherit_legacy_release_approval() -> None:
    settings = Settings(environment="test")

    assert settings.jioc_routing_approved_releases == [ROUTING_RELEASE]
    assert ROUTING_RELATIONAL_CAPACITY_RELEASE not in settings.jioc_routing_approved_releases

    report = evaluate_routing_release(
        _classify,
        approved_releases=settings.jioc_routing_approved_releases,
    )

    assert report.correct == report.total
    assert report.release_approved is False
    assert report.active_ready is False


def test_replay_cases_preserve_every_recorded_input() -> None:
    assert (
        tuple(
            replace(replay, case_id=base.case_id)
            for base, replay in zip(BASE_ROUTING_CASES, REPLAY_ROUTING_CASES, strict=True)
        )
        == BASE_ROUTING_CASES
    )


def test_leaf_coverage_is_an_independent_activation_gate() -> None:
    report = evaluate_routing_release(_classify)

    assert (
        replace(
            report,
            release_approved=True,
            delivery_leaves_covered=RELATIONAL_DELIVERY_LEAVES - {"cm_geo"},
        ).active_ready
        is False
    )


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
        tuple(
            f"{team_id}:{_capacity_status(case)}:{case.capacity_minutes or 0}"
            for team_id in candidate_ids
        ),
    )
    context = build_routing_context(ticket, snapshot, now)
    if not case.search_ready:
        context = replace(context, search_assurance="assisted", search_coverage="partial")
    disposition, route, _strength, codes, _questions = decide(ticket, context, rfa, cm)
    return RoutingEvaluationResult(disposition, route.value, codes)


def _capacity_status(case: RoutingEvaluationCase) -> str:
    demand = (
        RoutingDemandRange(
            case.delivery_leaf,
            case.demand_lower_minutes,
            case.demand_upper_minutes,
        )
        if case.demand_lower_minutes is not None and case.demand_upper_minutes is not None
        else None
    )
    return routing_capacity_status(case.capacity_minutes, demand)
