"""Bounded prompt and parser for the optional shadow routing critic model."""

import json
from enum import StrEnum
from typing import Any

from coeus.domain.enums import TicketState
from coeus.domain.jioc_routing import JiocRoutingContext, JiocRoutingDecision
from coeus.domain.routing_critic import (
    RoutingChallengeCode,
    RoutingCriticSeverity,
    RoutingCriticVerdict,
    RoutingCritiqueDraft,
    RoutingFactId,
    RoutingMissingEvidenceCode,
    RoutingReviewQuestionCode,
)
from coeus.domain.tickets import CmCapabilityReview, RfaCapabilityReview
from coeus.services.strict_json import load_unique_json

ROUTING_CRITIC_PROMPT_VERSION = "routing-critic-prompt-v1"
_MODEL_KEYS = frozenset(
    {
        "verdict",
        "challenge_codes",
        "missing_evidence_codes",
        "cited_fact_ids",
        "review_question_codes",
    }
)
_MAX_CODES = 16
C, M, F, Q = (
    RoutingChallengeCode,
    RoutingMissingEvidenceCode,
    RoutingFactId,
    RoutingReviewQuestionCode,
)


def routing_critic_prompt(
    context: JiocRoutingContext,
    decision: JiocRoutingDecision,
    rfa: RfaCapabilityReview,
    cm: CmCapabilityReview,
    committed_state: TicketState | str,
) -> str:
    """Expose structured facts only; narrative and workflow controls are excluded."""

    facts: dict[str, object] = {
        "context": _context_facts(context, decision, rfa, cm),
        "decision": {
            "recommended_route": decision.recommended_route,
            "disposition": decision.disposition,
            "confidence": decision.confidence,
            "rationale_codes": decision.rationale_codes,
            "required_clarification_count": len(decision.required_clarifications),
            "policy_version": decision.policy_version,
            "evidence_outcome": decision.evidence_outcome,
        },
        "reviews": {"rfa": _review_facts(rfa), "cm": _review_facts(cm)},
        "committed_state": _state_value(committed_state),
    }
    schema = {
        "verdict": ["supports", "challenges", "abstains"],
        "challenge_codes": list(C),
        "missing_evidence_codes": list(M),
        "cited_fact_ids": list(F),
        "review_question_codes": list(Q),
    }
    return (
        f"Prompt version: {ROUTING_CRITIC_PROMPT_VERSION}. "
        "Critique the consistency of the supplied facts. You are shadow-only. "
        "Do not propose routes, states, actions, dispositions, or tools. "
        "Return one JSON object with exactly these keys and allowlisted code values: "
        f"{json.dumps(schema, sort_keys=True)}\nFacts:"
        f"{json.dumps(facts, separators=(',', ':'), sort_keys=True)}"
    )


def parse_model_critique(raw: str) -> RoutingCritiqueDraft | None:
    """Reject extra keys, authority fields, duplicates and free-form values."""

    try:
        value = load_unique_json(raw)
        if not isinstance(value, dict) or set(value) != _MODEL_KEYS:
            return None
        provider_verdict = value["verdict"]
        if provider_verdict not in {"supports", "challenges", "abstains"}:
            return None
        challenges = _enum_list(value["challenge_codes"], RoutingChallengeCode)
        missing = _enum_list(value["missing_evidence_codes"], RoutingMissingEvidenceCode)
        facts = _enum_list(value["cited_fact_ids"], RoutingFactId)
        questions = _enum_list(value["review_question_codes"], RoutingReviewQuestionCode)
        if challenges is None or missing is None or facts is None or questions is None:
            return None
        if provider_verdict == "supports" and (challenges or missing or questions or not facts):
            return None
        if provider_verdict == "challenges" and (not (challenges or missing) or not facts):
            return None
        if provider_verdict == "abstains" and (challenges or questions):
            return None
        verdict = (
            RoutingCriticVerdict.SUPPORTS
            if provider_verdict == "supports"
            else RoutingCriticVerdict.CHALLENGES
            if provider_verdict == "challenges"
            else RoutingCriticVerdict.INSUFFICIENT_EVIDENCE
            if missing
            else RoutingCriticVerdict.UNAVAILABLE
        )
        severity = (
            RoutingCriticSeverity.WARNING if challenges or missing else RoutingCriticSeverity.INFO
        )
        return RoutingCritiqueDraft(verdict, severity, challenges, missing, facts, questions)
    except (AssertionError, json.JSONDecodeError, TypeError, ValueError):
        return None


def _review_facts(review: RfaCapabilityReview | CmCapabilityReview) -> dict[str, Any]:
    result = {
        "can_satisfy": review.can_satisfy,
        "confidence": review.confidence,
        "clarification_count": len(review.required_clarifications),
        "risk_count": len(review.risks),
        "manager_review_required": review.manager_review_required,
    }
    result["team_present"] = bool(
        review.suggested_team_id
        if isinstance(review, RfaCapabilityReview)
        else review.suggested_collection_team_id
    )
    return result


def _context_facts(
    context: JiocRoutingContext,
    decision: JiocRoutingDecision,
    rfa: RfaCapabilityReview,
    cm: CmCapabilityReview,
) -> dict[str, object]:
    return {
        "ticket_linkage_matches": (
            decision.ticket_id == context.ticket_id == rfa.ticket_id == cm.ticket_id
        ),
        "context_linkage_matches": decision.context_id == context.context_id,
        "schema_version": context.schema_version,
        "search_outcome": context.search_outcome,
        "search_assurance": context.search_assurance,
        "search_coverage": context.search_coverage,
        "search_corpus_present": bool(context.search_corpus_version),
        "product_offer_statuses": _status_values(context.product_offer_statuses),
        "active_work_search_completed": context.active_work_search_completed,
        "active_work_offer_statuses": _status_values(context.active_work_offer_statuses),
        "priority": context.priority,
        "deadline_present": bool(context.deadline),
        "output_format_present": bool(context.required_output_format),
        "discipline_present": bool(context.intelligence_disciplines),
        "area_present": bool(context.area_or_region),
        "time_window_present": bool(context.time_period_start or context.time_period_end),
        "restrictions_present": context.restrictions_present,
        "capability_catalogue_present": context.capability_catalogue_version != "unknown",
        "availability_snapshot_present": context.availability_snapshot_at is not None,
        "capacity_entry_count": len(context.candidate_capacity),
        "capacity_freshness_seconds": context.capacity_freshness_seconds,
    }


def _status_values(values: tuple[str, ...]) -> list[str]:
    return [value.rsplit(":", maxsplit=1)[-1] for value in values]


def _enum_list[E: StrEnum](value: Any, enum_type: type[E]) -> tuple[E, ...] | None:
    if not isinstance(value, list) or len(value) > _MAX_CODES:
        return None
    try:
        result = tuple(enum_type(item) for item in value if isinstance(item, str))
    except ValueError:
        return None
    if len(result) != len(value) or len(set(result)) != len(result):
        return None
    return result


def _state_value(state: TicketState | str) -> str:
    return state.value if isinstance(state, TicketState) else state
