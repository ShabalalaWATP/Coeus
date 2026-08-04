"""Versioned synthetic activation suite for deterministic JIOC routing."""

from collections.abc import Callable, Collection
from dataclasses import dataclass, replace

from coeus.domain.jioc_routing import (
    ROUTING_RELATIONAL_CAPACITY_EVALUATION_VERSION,
    ROUTING_RELATIONAL_CAPACITY_RELEASE,
)
from coeus.services.routing_demand_range import RELATIONAL_DELIVERY_LEAVES
from coeus.services.routing_evaluation_case import RoutingEvaluationCase
from coeus.services.routing_evaluation_counts import route_counts

MIN_EVALUATION_CASES = 48
MIN_CASE_ACCURACY = 1.0
MIN_CONFLICT_ACCURACY = 1.0


@dataclass(frozen=True)
class RoutingEvaluationResult:
    disposition: str
    route: str
    rationale_codes: tuple[str, ...]

    @property
    def routed_class(self) -> str:
        return self.route if self.disposition == "auto_applied" else "abstain"


@dataclass(frozen=True)
class RoutingEvaluationReport:
    evaluation_version: str
    release: str
    total: int
    correct: int
    unsafe_automatic_routes: int
    rfa_true_positives: int
    rfa_false_positives: int
    rfa_false_negatives: int
    cm_true_positives: int
    cm_false_positives: int
    cm_false_negatives: int
    conflict_total: int
    conflict_correct: int
    replay_mismatches: int
    expected_abstentions: int
    actual_abstentions: int
    delivery_leaves_covered: frozenset[str]
    release_approved: bool

    @property
    def case_accuracy(self) -> float:
        return self.correct / self.total if self.total else 0.0

    @property
    def conflict_accuracy(self) -> float:
        return self.conflict_correct / self.conflict_total if self.conflict_total else 0.0

    @property
    def abstention_rate(self) -> float:
        return self.actual_abstentions / self.total if self.total else 0.0

    @property
    def active_ready(self) -> bool:
        return (
            self.release_approved
            and self.total >= MIN_EVALUATION_CASES
            and self.case_accuracy >= MIN_CASE_ACCURACY
            and self.unsafe_automatic_routes == 0
            and self.rfa_false_positives == 0
            and self.rfa_false_negatives == 0
            and self.cm_false_positives == 0
            and self.cm_false_negatives == 0
            and self.conflict_accuracy >= MIN_CONFLICT_ACCURACY
            and self.replay_mismatches == 0
            and self.actual_abstentions == self.expected_abstentions
            and self.delivery_leaves_covered == RELATIONAL_DELIVERY_LEAVES
        )


def _case(
    case_id: str,
    description: str,
    output_format: str,
    expected_class: str,
    rationale: str,
    **overrides: object,
) -> RoutingEvaluationCase:
    disposition = "auto_applied" if expected_class in {"rfa", "cm"} else "manager_review"
    values = {
        "case_id": case_id,
        "description": description,
        "output_format": output_format,
        "expected_class": expected_class,
        "expected_disposition": disposition,
        "expected_rationale": rationale,
        **overrides,
    }
    return RoutingEvaluationCase(**values)  # type: ignore[arg-type]


BASE_ROUTING_CASES = (
    _case(
        "rfa-assess",
        "Assess the available reporting.",
        "assessment report",
        "rfa",
        "existing_information_assessment",
        delivery_leaf="rfa_maritime",
    ),
    _case(
        "rfa-analysis",
        "Analyse trends in existing reports.",
        "analysis",
        "rfa",
        "existing_information_assessment",
        delivery_leaf="rfa_land",
        capacity_minutes=600,
    ),
    _case(
        "rfa-brief",
        "Brief the duty officer using current holdings.",
        "briefing",
        "rfa",
        "existing_information_assessment",
        delivery_leaf="rfa_cyber",
    ),
    _case(
        "rfa-estimate",
        "Estimate likely disruption from known context.",
        "estimate",
        "rfa",
        "existing_information_assessment",
        delivery_leaf="rfa_regional",
    ),
    _case(
        "cm-monitor",
        "Monitor the mock area with sensors.",
        "collection plan",
        "cm",
        "new_collection_required",
        delivery_leaf="cm_open",
    ),
    _case(
        "cm-surveillance",
        "Conduct surveillance of the mock port.",
        "collection plan",
        "cm",
        "new_collection_required",
        delivery_leaf="cm_geo",
    ),
    _case(
        "cm-imagery",
        "Collect new imagery of the mock harbour.",
        "imagery collection",
        "cm",
        "new_collection_required",
        delivery_leaf="cm_requirements",
    ),
    _case(
        "cm-source",
        "Task a source to monitor the mock exercise.",
        "collection plan",
        "abstain",
        "team_capacity_missing",
        demand_lower_minutes=None,
        demand_upper_minutes=None,
    ),
    _case(
        "mixed-assess-collect",
        "Assess reports and collect new imagery.",
        "assessment report",
        "abstain",
        "conflicting_route_signals",
    ),
    _case(
        "mixed-brief-monitor",
        "Brief current holdings and monitor with sensors.",
        "briefing",
        "abstain",
        "conflicting_route_signals",
    ),
    _case(
        "negated-collection",
        "Assess reports without new collection.",
        "assessment report",
        "abstain",
        "risk_review_required",
    ),
    _case(
        "capacity-inside-demand-range",
        "Assess the available reporting.",
        "assessment report",
        "abstain",
        "team_capacity_unavailable",
        capacity_minutes=360,
    ),
    _case(
        "missing-search",
        "Assess the available reporting.",
        "assessment report",
        "abstain",
        "product_search_not_definitive",
        search_ready=False,
    ),
    _case(
        "stale-capacity",
        "Assess the available reporting.",
        "assessment report",
        "abstain",
        "availability_snapshot_stale",
        snapshot_age_seconds=301,
    ),
    _case(
        "missing-capacity-snapshot",
        "Assess available reporting.",
        "assessment report",
        "abstain",
        "availability_snapshot_missing",
        snapshot_present=False,
    ),
    _case(
        "unknown-capacity",
        "Assess available reporting.",
        "assessment report",
        "abstain",
        "team_capacity_missing",
        capacity_minutes=None,
    ),
    _case(
        "capacity-below-demand-range",
        "Monitor the area with sensors.",
        "collection plan",
        "abstain",
        "team_capacity_unavailable",
        capacity_minutes=225,
    ),
    _case(
        "critical-missing-deadline",
        "Monitor the area with sensors.",
        "collection plan",
        "abstain",
        "clarification_required",
        priority="critical",
        deadline=None,
        expected_disposition="clarification",
    ),
    _case(
        "unsupported-scope",
        "Assess activity on Mars.",
        "assessment report",
        "abstain",
        "clarification_required",
        expected_disposition="clarification",
    ),
    _case(
        "restricted",
        "Assess the available reporting.",
        "assessment report",
        "abstain",
        "risk_review_required",
        restrictions="Manager handling required.",
    ),
    _case(
        "unresolved-product",
        "Assess the available reporting.",
        "assessment report",
        "abstain",
        "product_offer_unresolved",
        product_offer_unresolved=True,
    ),
    _case(
        "missing-active-search",
        "Assess the available reporting.",
        "assessment report",
        "abstain",
        "active_work_search_missing",
        active_work_completed=False,
    ),
    _case(
        "unresolved-active-offer",
        "Assess available reporting.",
        "assessment report",
        "abstain",
        "active_work_offer_unresolved",
        active_work_offer_unresolved=True,
    ),
    _case(
        "no-route-evidence",
        "Summarise the mock exercise overview.",
        "summary",
        "abstain",
        "insufficient_route_evidence",
    ),
)

REPLAY_ROUTING_CASES = tuple(
    replace(case, case_id=f"{case.case_id}-replay") for case in BASE_ROUTING_CASES
)

LABELLED_ROUTING_CASES = (*BASE_ROUTING_CASES, *REPLAY_ROUTING_CASES)


def evaluate_routing_release(
    classify: Callable[[RoutingEvaluationCase], RoutingEvaluationResult],
    *,
    approved_releases: Collection[str] = (),
) -> RoutingEvaluationReport:
    results = tuple((case, classify(case)) for case in LABELLED_ROUTING_CASES)
    correct = sum(
        result.routed_class == case.expected_class
        and result.disposition == case.expected_disposition
        and case.expected_rationale in result.rationale_codes
        for case, result in results
    )
    unsafe = sum(
        result.disposition == "auto_applied" and case.expected_class == "abstain"
        for case, result in results
    )
    conflict = tuple(
        (case, result)
        for case, result in results
        if case.expected_rationale == "conflicting_route_signals"
    )
    expected_abstentions = sum(case.expected_class == "abstain" for case, _ in results)
    actual_abstentions = sum(result.routed_class == "abstain" for _, result in results)
    by_id = {case.case_id: result for case, result in results}
    replay_mismatches = sum(
        result != by_id[case.case_id.removesuffix("-replay")]
        for case, result in results
        if case.case_id.endswith("-replay")
    )
    outcomes = tuple((case.expected_class, result.routed_class) for case, result in results)
    return RoutingEvaluationReport(
        ROUTING_RELATIONAL_CAPACITY_EVALUATION_VERSION,
        ROUTING_RELATIONAL_CAPACITY_RELEASE,
        len(results),
        correct,
        unsafe,
        *(route_counts("rfa", outcomes)),
        *(route_counts("cm", outcomes)),
        len(conflict),
        sum("conflicting_route_signals" in result.rationale_codes for _, result in conflict),
        replay_mismatches,
        expected_abstentions,
        actual_abstentions,
        frozenset(case.delivery_leaf for case, _ in results),
        ROUTING_RELATIONAL_CAPACITY_RELEASE in approved_releases,
    )
