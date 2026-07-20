"""Versioned synthetic activation suite for deterministic JIOC routing."""

from collections.abc import Callable
from dataclasses import dataclass

from coeus.domain.jioc_routing import ROUTING_EVALUATION_VERSION, ROUTING_RELEASE

MIN_EVALUATION_CASES = 16
MIN_CASE_ACCURACY = 1.0
MIN_CONFLICT_ACCURACY = 1.0


@dataclass(frozen=True)
class RoutingEvaluationCase:
    case_id: str
    description: str
    output_format: str
    expected_class: str
    expected_disposition: str
    expected_rationale: str
    search_ready: bool = True
    capacity: str = "available"
    snapshot_age_seconds: int = 0
    snapshot_present: bool = True
    priority: str = "routine"
    deadline: str | None = "2026-07-21"
    restrictions: str | None = None
    product_offer_unresolved: bool = False
    active_work_completed: bool = True
    active_work_offer_unresolved: bool = False


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
    expected_abstentions: int
    actual_abstentions: int

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
            self.total >= MIN_EVALUATION_CASES
            and self.case_accuracy >= MIN_CASE_ACCURACY
            and self.unsafe_automatic_routes == 0
            and self.rfa_false_positives == 0
            and self.rfa_false_negatives == 0
            and self.cm_false_positives == 0
            and self.cm_false_negatives == 0
            and self.conflict_accuracy >= MIN_CONFLICT_ACCURACY
            and self.actual_abstentions == self.expected_abstentions
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


LABELLED_ROUTING_CASES = (
    _case(
        "rfa-assess",
        "Assess the available reporting.",
        "assessment report",
        "rfa",
        "existing_information_assessment",
    ),
    _case(
        "rfa-analysis",
        "Analyse trends in existing reports.",
        "analysis",
        "rfa",
        "existing_information_assessment",
    ),
    _case(
        "rfa-brief",
        "Brief the duty officer using current holdings.",
        "briefing",
        "rfa",
        "existing_information_assessment",
    ),
    _case(
        "rfa-estimate",
        "Estimate likely disruption from known context.",
        "estimate",
        "rfa",
        "existing_information_assessment",
    ),
    _case(
        "cm-monitor",
        "Monitor the mock area with sensors.",
        "collection plan",
        "cm",
        "new_collection_required",
    ),
    _case(
        "cm-surveillance",
        "Conduct surveillance of the mock port.",
        "collection plan",
        "cm",
        "new_collection_required",
    ),
    _case(
        "cm-imagery",
        "Collect new imagery of the mock harbour.",
        "imagery collection",
        "cm",
        "new_collection_required",
    ),
    _case(
        "cm-source",
        "Task a source to monitor the mock exercise.",
        "collection plan",
        "cm",
        "new_collection_required",
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
        "negated-assessment",
        "Monitor the area, do not produce an assessment.",
        "collection plan",
        "abstain",
        "risk_review_required",
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
        capacity="unknown",
    ),
    _case(
        "unavailable-capacity",
        "Monitor the area with sensors.",
        "collection plan",
        "abstain",
        "team_capacity_unavailable",
        capacity="unavailable",
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


def evaluate_routing_release(
    classify: Callable[[RoutingEvaluationCase], RoutingEvaluationResult],
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
    return RoutingEvaluationReport(
        ROUTING_EVALUATION_VERSION,
        ROUTING_RELEASE,
        len(results),
        correct,
        unsafe,
        *(_route_counts("rfa", results)),
        *(_route_counts("cm", results)),
        len(conflict),
        sum("conflicting_route_signals" in result.rationale_codes for _, result in conflict),
        expected_abstentions,
        actual_abstentions,
    )


def _route_counts(
    route: str,
    results: tuple[tuple[RoutingEvaluationCase, RoutingEvaluationResult], ...],
) -> tuple[int, int, int]:
    true_positive = sum(
        case.expected_class == route and result.routed_class == route for case, result in results
    )
    false_positive = sum(
        case.expected_class != route and result.routed_class == route for case, result in results
    )
    false_negative = sum(
        case.expected_class == route and result.routed_class != route for case, result in results
    )
    return true_positive, false_positive, false_negative
