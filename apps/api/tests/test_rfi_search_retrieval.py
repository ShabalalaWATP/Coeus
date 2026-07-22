from types import SimpleNamespace
from uuid import uuid4

from coeus.domain.enums import TicketState
from coeus.domain.search_index import GroundedSearchResult
from coeus.domain.tickets import IntakeDetails, ProductOffer, ProductOfferStatus
from coeus.services.rfi_search_assurance import decide_search_outcome
from coeus.services.rfi_search_retrieval import (
    PlannedRetrieval,
    ranked_additive_offers,
    retrieve_with_additive_advice,
)
from coeus.services.search_planner import EMPTY_SEARCH_PLANNER_ADVICE, SearchPlannerAdvice


def _offer(title: str, product_id=None) -> ProductOffer:  # type: ignore[no-untyped-def]
    return ProductOffer(
        product_id=product_id or uuid4(),
        title=title,
        summary="Synthetic summary",
        product_type="ASSESSMENT",
        match_score=0.9,
        match_reasons=("full-text:synthetic",),
        classification_level=1,
        releasability=("MOCK",),
        region="Synthetic Region",
        time_period_start=None,
        time_period_end=None,
        asset_types=(),
        offerable_to_user=True,
        status=ProductOfferStatus.OFFERED,
    )


def test_supplemental_results_cannot_displace_or_duplicate_baseline_offers(monkeypatch) -> None:
    baseline = tuple(_offer(f"Baseline {index}") for index in range(5))
    supplemental = (_offer("Duplicate", baseline[0].product_id), _offer("Additional"))
    retrieval = PlannedRetrieval(
        "base",
        "base plus hints",
        SimpleNamespace(),  # type: ignore[arg-type]
        ("baseline-candidates",),  # type: ignore[arg-type]
        ("supplemental-candidates",),  # type: ignore[arg-type]
        GroundedSearchResult((), "hybrid", None, "space-v1", "complete", "corpus-v1"),
    )

    def rank(candidates, _intake):  # type: ignore[no-untyped-def]
        return baseline if candidates == ("baseline-candidates",) else supplemental

    monkeypatch.setattr("coeus.services.rfi_search_retrieval.rank_hybrid_rfi_candidates", rank)

    offers = ranked_additive_offers(
        retrieval,
        SimpleNamespace(intake=SimpleNamespace()),  # type: ignore[arg-type]
    )

    assert offers == baseline
    assert tuple(offer.title for offer in offers) == tuple(
        f"Baseline {index}" for index in range(5)
    )


def test_baseline_retrieval_runs_before_optional_planner(monkeypatch) -> None:
    events: list[str] = []
    grounded = GroundedSearchResult((), "hybrid", None, "space-v1", "complete", "corpus-v1")

    def retrieve(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        events.append("baseline")
        return (), grounded

    class Planner:
        def plan_safely(self, *_args):  # type: ignore[no-untyped-def]
            events.append("planner")
            return SimpleNamespace(suggestions=EMPTY_SEARCH_PLANNER_ADVICE, record=object())

    monkeypatch.setattr("coeus.services.rfi_search_retrieval._retrieve_leg", retrieve)
    requester_id = uuid4()
    retrieval = retrieve_with_additive_advice(
        SimpleNamespace(),  # type: ignore[arg-type]
        SimpleNamespace(requester_user_id=requester_id, intake=IntakeDetails()),  # type: ignore[arg-type]
        requester_id,
        Planner(),  # type: ignore[arg-type]
        SimpleNamespace(),  # type: ignore[arg-type]
        SimpleNamespace(),  # type: ignore[arg-type]
        SimpleNamespace(),  # type: ignore[arg-type]
        SimpleNamespace(),  # type: ignore[arg-type]
    )

    assert events == ["baseline", "planner"]
    assert retrieval.baseline_candidates == ()


def test_supplemental_failure_preserves_baseline_and_degrades_assurance(monkeypatch) -> None:
    events: list[str] = []
    grounded = GroundedSearchResult((), "hybrid", None, "space-v1", "complete", "corpus-v1")

    def retrieve(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        events.append("retrieve")
        if len(events) == 2:
            raise RuntimeError("synthetic supplemental failure with sensitive detail")
        return ("authorised-baseline",), grounded

    class Planner:
        def plan_safely(self, *_args):  # type: ignore[no-untyped-def]
            return SimpleNamespace(
                suggestions=SearchPlannerAdvice(query_expansions=("bounded hint",)),
                record=object(),
            )

    monkeypatch.setattr("coeus.services.rfi_search_retrieval._retrieve_leg", retrieve)
    requester_id = uuid4()
    retrieval = retrieve_with_additive_advice(
        SimpleNamespace(),  # type: ignore[arg-type]
        SimpleNamespace(  # type: ignore[arg-type]
            requester_user_id=requester_id,
            intake=IntakeDetails(description="authorised baseline query"),
        ),
        requester_id,
        Planner(),  # type: ignore[arg-type]
        SimpleNamespace(),  # type: ignore[arg-type]
        SimpleNamespace(),  # type: ignore[arg-type]
        SimpleNamespace(),  # type: ignore[arg-type]
        SimpleNamespace(),  # type: ignore[arg-type]
    )

    assert events == ["retrieve", "retrieve"]
    assert retrieval.baseline_candidates == ("authorised-baseline",)
    assert retrieval.supplemental_candidates == ()
    assert retrieval.grounded.coverage_status == "partial"
    assert retrieval.grounded.degraded_reason == "supplemental_search_failed"
    assert "sensitive" not in retrieval.grounded.degraded_reason
    decision = decide_search_outcome(0, retrieval.grounded)
    assert decision.state is TicketState.RFI_SEARCH_INCOMPLETE
    assert decision.assurance == "assisted"
