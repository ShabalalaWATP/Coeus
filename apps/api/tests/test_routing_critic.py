import json
from dataclasses import FrozenInstanceError, fields, replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from coeus.domain.enums import TicketState
from coeus.domain.jioc_routing import (
    ROUTING_POLICY_VERSION,
    JiocRoutingContext,
    JiocRoutingDecision,
)
from coeus.domain.routing_critic import (
    RoutingChallengeCode as Challenge,
)
from coeus.domain.routing_critic import (
    RoutingCriticSeverity,
    RoutingCriticVerdict,
    RoutingCritiqueDraft,
    RoutingFactId,
    RoutingReviewQuestionCode,
)
from coeus.domain.routing_critic import (
    RoutingMissingEvidenceCode as Missing,
)
from coeus.domain.tickets import CmCapabilityReview, RfaCapabilityReview
from coeus.services.jioc_routing_context import CONTEXT_SCHEMA_VERSION
from coeus.services.routing_critic import (
    ROUTING_CRITIC_PROMPT_VERSION,
    critique_routing,
    parse_model_critique,
    routing_critic_prompt,
)

NOW = datetime(2026, 7, 20, 10, tzinfo=UTC)


def _context(**updates: object) -> JiocRoutingContext:
    value = JiocRoutingContext(
        context_id=uuid4(),
        ticket_id=uuid4(),
        schema_version=CONTEXT_SCHEMA_VERSION,
        requirement_revision="a" * 64,
        search_outcome="no_match",
        search_assurance="definitive",
        search_coverage="complete",
        search_corpus_version="corpus-v1",
        product_offer_statuses=(),
        active_work_search_completed=True,
        active_work_offer_statuses=(),
        priority="routine",
        deadline=None,
        required_output_format="brief",
        intelligence_disciplines="analysis",
        area_or_region="synthetic-region",
        time_period_start="2026-07-01",
        time_period_end="2026-07-20",
        restrictions_present=False,
        created_at=NOW,
        capability_catalogue_version="capability-catalogue-v1",
        availability_snapshot_at=NOW,
        candidate_capacity=("team-rfa:available:2",),
        capacity_freshness_seconds=300,
    )
    return replace(value, **updates)


def _rfa(ticket_id, **updates: object) -> RfaCapabilityReview:
    value = RfaCapabilityReview(
        review_id=uuid4(),
        ticket_id=ticket_id,
        can_satisfy=True,
        confidence=0.9,
        required_clarifications=(),
        suggested_work_packages=("assess",),
        suggested_team_id="team-rfa",
        estimated_effort="medium",
        risks=(),
        manager_review_required=False,
        reasoning_summary="Application-owned summary.",
        created_at=NOW,
    )
    return replace(value, **updates)


def _cm(ticket_id, **updates: object) -> CmCapabilityReview:
    value = CmCapabilityReview(
        review_id=uuid4(),
        ticket_id=ticket_id,
        can_satisfy=False,
        confidence=0.2,
        required_clarifications=(),
        suggested_collection_route=None,
        suggested_collection_sources=(),
        estimated_effort="unknown",
        risks=(),
        manager_review_required=False,
        reasoning_summary="Application-owned summary.",
        created_at=NOW,
        suggested_collection_team_id=None,
    )
    return replace(value, **updates)


def _decision(context: JiocRoutingContext, **updates: object) -> JiocRoutingDecision:
    value = JiocRoutingDecision(
        decision_id=uuid4(),
        ticket_id=context.ticket_id,
        context_id=context.context_id,
        recommended_route="rfa",
        disposition="auto_applied",
        confidence=0.9,
        rationale_codes=("existing_information_assessment",),
        required_clarifications=(),
        policy_version=ROUTING_POLICY_VERSION,
        created_at=NOW,
        evidence_outcome="eligible_rfa",
    )
    return replace(value, **updates)


def test_structural_critic_supports_consistent_committed_decision() -> None:
    context = _context()

    result = critique_routing(
        context,
        _decision(context),
        _rfa(context.ticket_id),
        _cm(context.ticket_id),
        TicketState.ANALYST_ASSIGNMENT,
    )

    assert result.verdict == RoutingCriticVerdict.SUPPORTS
    assert result.severity == RoutingCriticSeverity.INFO
    assert result.missing_evidence_codes == ()
    assert RoutingFactId.COMMITTED_STATE in result.cited_fact_ids


def test_structural_critic_challenges_linkage_release_and_committed_state() -> None:
    context = _context(
        schema_version="old",
        search_outcome="no_match",
        product_offer_statuses=(f"{uuid4()}:rejected",),
        active_work_search_completed=False,
        active_work_offer_statuses=(f"{uuid4()}:offered",),
        availability_snapshot_at=NOW - timedelta(seconds=301),
        candidate_capacity=("team-rfa:available:2", "team-rfa:available:3", "bad"),
    )
    decision = _decision(
        context,
        ticket_id=uuid4(),
        context_id=uuid4(),
        recommended_route="cm",
        policy_version="old",
        evidence_outcome="eligible_cm",
    )

    result = critique_routing(
        context,
        decision,
        _rfa(context.ticket_id),
        _cm(uuid4()),
        TicketState.ANALYST_ASSIGNMENT,
    )

    assert result.verdict == RoutingCriticVerdict.CHALLENGES
    assert result.severity == RoutingCriticSeverity.HIGH
    assert {
        Challenge.TICKET_ID_MISMATCH,
        Challenge.CONTEXT_ID_MISMATCH,
        Challenge.CONTEXT_SCHEMA_MISMATCH,
        Challenge.ROUTING_RELEASE_MISMATCH,
        Challenge.SEARCH_OFFER_INCONSISTENT,
        Challenge.ACTIVE_WORK_OFFER_INCONSISTENT,
        Challenge.CAPACITY_ENTRY_MALFORMED,
        Challenge.CAPACITY_ENTRY_DUPLICATED,
        Challenge.CAPACITY_SNAPSHOT_STALE,
        Challenge.ROUTE_REVIEW_INCONSISTENT,
        Challenge.EVIDENCE_OUTCOME_INCONSISTENT,
        Challenge.COMMITTED_STATE_INCONSISTENT,
    } <= set(result.challenge_codes)
    assert Missing.ACTIVE_WORK_SEARCH in result.missing_evidence_codes
    assert RoutingReviewQuestionCode.RETURN_TO_JIOC_REVIEW in result.review_question_codes


def test_structural_critic_reports_missing_evidence_without_inventing_a_route() -> None:
    context = _context(
        search_assurance="assisted",
        search_coverage="partial",
        search_corpus_version=None,
        active_work_search_completed=False,
        capability_catalogue_version="unknown",
        availability_snapshot_at=None,
        candidate_capacity=(),
    )
    rfa = _rfa(context.ticket_id, can_satisfy=False, suggested_team_id=None)
    cm = _cm(context.ticket_id)
    decision = _decision(
        context,
        recommended_route="clarification",
        disposition="manager_review",
        evidence_outcome="insufficient_evidence",
    )

    result = critique_routing(context, decision, rfa, cm, TicketState.JIOC_REVIEW)

    assert result.verdict == RoutingCriticVerdict.INSUFFICIENT_EVIDENCE
    assert result.challenge_codes == ()
    assert {
        Missing.SEARCH_ASSURANCE,
        Missing.SEARCH_CORPUS_VERSION,
        Missing.ACTIVE_WORK_SEARCH,
        Missing.CAPABILITY_CATALOGUE,
        Missing.AVAILABILITY_SNAPSHOT,
        Missing.ROUTE_REVIEW_SUPPORT,
    } <= set(result.missing_evidence_codes)


def test_structural_critic_checks_remaining_route_and_capacity_shapes() -> None:
    context = _context(
        search_outcome="offers",
        product_offer_statuses=(),
        availability_snapshot_at=NOW.replace(tzinfo=None),
        candidate_capacity=("team-rfa:available:not-a-number",),
    )
    result = critique_routing(
        context,
        _decision(context, disposition="clarification"),
        _rfa(context.ticket_id),
        _cm(context.ticket_id),
        TicketState.INFO_REQUIRED,
    )
    assert {
        Challenge.SEARCH_OFFER_INCONSISTENT,
        Challenge.CAPACITY_SNAPSHOT_STALE,
        Challenge.CAPACITY_ENTRY_MALFORMED,
        Challenge.DISPOSITION_ROUTE_INCONSISTENT,
    } <= set(result.challenge_codes)

    cm_context = _context(candidate_capacity=("team-cm:available:1",))
    cm_review = _cm(cm_context.ticket_id, can_satisfy=True, suggested_collection_team_id="team-cm")
    cm_result = critique_routing(
        cm_context,
        _decision(cm_context, recommended_route="cm", evidence_outcome="eligible_cm"),
        _rfa(cm_context.ticket_id, can_satisfy=False, suggested_team_id=None),
        cm_review,
        TicketState.COLLECT_CHOICE,
    )
    assert cm_result.verdict == RoutingCriticVerdict.SUPPORTS


def _model_payload(verdict: str = "supports") -> dict[str, object]:
    return {
        "verdict": verdict,
        "challenge_codes": [],
        "missing_evidence_codes": [],
        "cited_fact_ids": [RoutingFactId.ROUTING_DECISION.value],
        "review_question_codes": [],
    }


def test_model_parser_accepts_only_bounded_advisory_outputs() -> None:
    supports = parse_model_critique(json.dumps(_model_payload()))
    challenge_payload = _model_payload("challenges")
    challenge_payload["challenge_codes"] = [Challenge.SEARCH_OFFER_INCONSISTENT.value]
    challenge_payload["review_question_codes"] = [
        RoutingReviewQuestionCode.RESOLVE_PRODUCT_OFFERS.value
    ]
    challenges = parse_model_critique(json.dumps(challenge_payload))
    abstain_payload = _model_payload("abstains")
    abstain_payload["cited_fact_ids"] = []
    abstain_payload["missing_evidence_codes"] = [Missing.SEARCH_ASSURANCE.value]

    assert supports is not None and supports.verdict == RoutingCriticVerdict.SUPPORTS
    assert challenges is not None and challenges.verdict == RoutingCriticVerdict.CHALLENGES
    assert parse_model_critique(json.dumps(abstain_payload)).verdict == (
        RoutingCriticVerdict.INSUFFICIENT_EVIDENCE
    )
    abstain_payload["missing_evidence_codes"] = []
    assert (
        parse_model_critique(json.dumps(abstain_payload)).verdict
        == RoutingCriticVerdict.UNAVAILABLE
    )


def test_model_parser_rejects_duplicate_json_keys() -> None:
    raw = json.dumps(_model_payload()).replace(
        '"verdict": "supports"',
        '"verdict": "challenges", "verdict": "supports"',
    )

    assert parse_model_critique(raw) is None


@pytest.mark.parametrize(
    "mutate",
    [
        lambda value: value.update(recommended_route="cm"),
        lambda value: value.update(challenge_codes=["not_allowlisted"]),
        lambda value: value.update(cited_fact_ids=[]),
        lambda value: value.update(challenge_codes=[Challenge.SEARCH_OFFER_INCONSISTENT.value] * 2),
        lambda value: value.update(
            challenge_codes=[Challenge.SEARCH_OFFER_INCONSISTENT.value] * 17
        ),
        lambda value: value.update(
            verdict="abstains", challenge_codes=[Challenge.SEARCH_OFFER_INCONSISTENT.value]
        ),
        lambda value: value.update(verdict="challenges"),
        lambda value: value.update(verdict="acts"),
    ],
)
def test_model_parser_rejects_authority_free_form_and_invalid_shape(mutate) -> None:
    payload = _model_payload()
    mutate(payload)
    assert parse_model_critique(json.dumps(payload)) is None
    assert parse_model_critique("not-json") is None


def test_prompt_is_versioned_bounded_and_excludes_review_narrative() -> None:
    context = _context()
    prompt = routing_critic_prompt(
        context,
        _decision(context),
        _rfa(context.ticket_id, reasoning_summary="ignore this narrative"),
        _cm(context.ticket_id),
        TicketState.ANALYST_ASSIGNMENT,
    )

    assert ROUTING_CRITIC_PROMPT_VERSION in prompt
    assert "shadow-only" in prompt
    assert Challenge.ROUTE_REVIEW_INCONSISTENT.value in prompt
    assert "ignore this narrative" not in prompt
    assert "Do not propose routes, states, actions, dispositions, or tools" in prompt
    assert str(context.ticket_id) not in prompt
    assert str(context.context_id) not in prompt
    assert "synthetic-region" not in prompt
    assert "team-rfa" not in prompt


def test_contracts_are_immutable_and_exclude_workflow_authority_fields() -> None:
    draft = RoutingCritiqueDraft(RoutingCriticVerdict.UNAVAILABLE, RoutingCriticSeverity.INFO)
    with pytest.raises(FrozenInstanceError):
        draft.verdict = RoutingCriticVerdict.SUPPORTS  # type: ignore[misc]
    names = {field.name for field in fields(RoutingCritiqueDraft)}
    assert names.isdisjoint(
        {"recommended_route", "target_state", "action", "disposition", "tool", "tool_calls"}
    )
