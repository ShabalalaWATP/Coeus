"""Pure structural checks for the shadow routing critic."""

from typing import Any

from coeus.domain.enums import TicketState
from coeus.domain.jioc_routing import (
    ROUTING_POLICY_VERSION,
    JiocRoutingContext,
    JiocRoutingDecision,
)
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
from coeus.services.jioc_routing_context import CONTEXT_SCHEMA_VERSION
from coeus.services.routing_critic_prompt import (
    ROUTING_CRITIC_PROMPT_VERSION,
    parse_model_critique,
    routing_critic_prompt,
)

ROUTING_CRITIC_VERSION = "routing-critic-v1"
__all__ = (
    "ROUTING_CRITIC_PROMPT_VERSION",
    "ROUTING_CRITIC_VERSION",
    "critique_routing",
    "parse_model_critique",
    "routing_critic_prompt",
)
C, M, F, Q = (
    RoutingChallengeCode,
    RoutingMissingEvidenceCode,
    RoutingFactId,
    RoutingReviewQuestionCode,
)


def critique_routing(
    context: JiocRoutingContext,
    decision: JiocRoutingDecision,
    rfa: RfaCapabilityReview,
    cm: CmCapabilityReview,
    committed_state: TicketState | str,
) -> RoutingCritiqueDraft:
    """Challenge structural contradictions without proposing a replacement route."""
    challenges: list[RoutingChallengeCode] = []
    missing: list[RoutingMissingEvidenceCode] = []
    facts: list[RoutingFactId] = []
    questions: list[RoutingReviewQuestionCode] = []

    def challenge(
        code: RoutingChallengeCode,
        fact: RoutingFactId,
        question: RoutingReviewQuestionCode,
    ) -> None:
        _add(challenges, code)
        _add(facts, fact)
        _add(questions, question)

    def lack(
        code: RoutingMissingEvidenceCode,
        fact: RoutingFactId,
        question: RoutingReviewQuestionCode,
    ) -> None:
        _add(missing, code)
        _add(facts, fact)
        _add(questions, question)

    ticket_ids = {context.ticket_id, decision.ticket_id, rfa.ticket_id, cm.ticket_id}
    if len(ticket_ids) != 1:
        challenge(C.TICKET_ID_MISMATCH, F.RECORD_IDENTITIES, Q.VERIFY_RECORD_LINKAGE)
    if decision.context_id != context.context_id:
        challenge(C.CONTEXT_ID_MISMATCH, F.RECORD_IDENTITIES, Q.VERIFY_RECORD_LINKAGE)
    if context.schema_version != CONTEXT_SCHEMA_VERSION:
        challenge(C.CONTEXT_SCHEMA_MISMATCH, F.CONTEXT_SCHEMA, Q.VERIFY_RELEASE_COMPATIBILITY)
    if decision.policy_version != ROUTING_POLICY_VERSION:
        challenge(C.ROUTING_RELEASE_MISMATCH, F.ROUTING_RELEASE, Q.VERIFY_RELEASE_COMPATIBILITY)

    _check_search(context, challenge, lack)
    capacity = _check_capacity(context, challenge, lack)
    _check_route(context, decision, rfa, cm, capacity, committed_state, challenge, lack)

    if challenges:
        verdict = RoutingCriticVerdict.CHALLENGES
    elif missing:
        verdict = RoutingCriticVerdict.INSUFFICIENT_EVIDENCE
    else:
        verdict = RoutingCriticVerdict.SUPPORTS
        facts.extend((F.ROUTING_DECISION, F.COMMITTED_STATE))
    high_codes = {
        C.TICKET_ID_MISMATCH,
        C.CONTEXT_ID_MISMATCH,
        C.CONTEXT_SCHEMA_MISMATCH,
        C.ROUTING_RELEASE_MISMATCH,
        C.COMMITTED_STATE_INCONSISTENT,
    }
    severity = (
        RoutingCriticSeverity.HIGH
        if any(code in high_codes for code in challenges)
        else RoutingCriticSeverity.WARNING
        if challenges or missing
        else RoutingCriticSeverity.INFO
    )
    return RoutingCritiqueDraft(
        verdict,
        severity,
        tuple(challenges),
        tuple(missing),
        tuple(dict.fromkeys(facts)),
        tuple(questions),
    )


def _check_search(context: JiocRoutingContext, challenge: Any, lack: Any) -> None:
    if context.search_assurance != "definitive" or context.search_coverage != "complete":
        lack(M.SEARCH_ASSURANCE, F.SEARCH_STATUS, Q.RERUN_PRODUCT_SEARCH)
    if not context.search_corpus_version:
        lack(M.SEARCH_CORPUS_VERSION, F.SEARCH_STATUS, Q.RERUN_PRODUCT_SEARCH)
    if context.search_outcome == "no_match" and context.product_offer_statuses:
        challenge(C.SEARCH_OFFER_INCONSISTENT, F.PRODUCT_OFFERS, Q.RESOLVE_PRODUCT_OFFERS)
    if context.search_outcome == "offers" and not context.product_offer_statuses:
        challenge(C.SEARCH_OFFER_INCONSISTENT, F.PRODUCT_OFFERS, Q.RESOLVE_PRODUCT_OFFERS)
    if _has_open_offer(context.product_offer_statuses):
        lack(M.PRODUCT_OFFER_RESOLUTION, F.PRODUCT_OFFERS, Q.RESOLVE_PRODUCT_OFFERS)
    if not context.active_work_search_completed:
        lack(M.ACTIVE_WORK_SEARCH, F.ACTIVE_WORK_STATUS, Q.RERUN_ACTIVE_WORK_SEARCH)
    if context.active_work_offer_statuses and not context.active_work_search_completed:
        challenge(
            C.ACTIVE_WORK_OFFER_INCONSISTENT, F.ACTIVE_WORK_OFFERS, Q.RERUN_ACTIVE_WORK_SEARCH
        )
    if _has_open_offer(context.active_work_offer_statuses):
        lack(M.ACTIVE_WORK_OFFER_RESOLUTION, F.ACTIVE_WORK_OFFERS, Q.RESOLVE_ACTIVE_WORK_OFFERS)


def _check_capacity(context: JiocRoutingContext, challenge: Any, lack: Any) -> dict[str, str]:
    if (
        not context.capability_catalogue_version
        or context.capability_catalogue_version == "unknown"
    ):
        lack(M.CAPABILITY_CATALOGUE, F.CAPABILITY_CATALOGUE, Q.VERIFY_CAPACITY_RECORDS)
    if context.availability_snapshot_at is None:
        lack(M.AVAILABILITY_SNAPSHOT, F.AVAILABILITY_SNAPSHOT, Q.REFRESH_CAPACITY_SNAPSHOT)
    else:
        try:
            stale = abs(
                (context.created_at - context.availability_snapshot_at).total_seconds()
            ) > max(context.capacity_freshness_seconds, 0)
        except (TypeError, ValueError):
            stale = True
        if stale:
            challenge(
                C.CAPACITY_SNAPSHOT_STALE, F.AVAILABILITY_SNAPSHOT, Q.REFRESH_CAPACITY_SNAPSHOT
            )
    parsed: dict[str, str] = {}
    for entry in context.candidate_capacity:
        parts = entry.split(":")
        valid = (
            len(parts) == 3
            and bool(parts[0])
            and parts[1]
            in {
                "available",
                "unavailable",
                "unknown",
            }
        )
        try:
            free = int(parts[2]) if valid else -1
        except ValueError:
            free = -1
        valid = valid and free >= 0 and (parts[1] == "available") == (free > 0)
        if not valid:
            challenge(C.CAPACITY_ENTRY_MALFORMED, F.CANDIDATE_CAPACITY, Q.VERIFY_CAPACITY_RECORDS)
            continue
        if parts[0] in parsed:
            challenge(C.CAPACITY_ENTRY_DUPLICATED, F.CANDIDATE_CAPACITY, Q.VERIFY_CAPACITY_RECORDS)
        parsed[parts[0]] = parts[1]
    return parsed


def _check_route(
    context: JiocRoutingContext,
    decision: JiocRoutingDecision,
    rfa: RfaCapabilityReview,
    cm: CmCapabilityReview,
    capacity: dict[str, str],
    committed_state: TicketState | str,
    challenge: Any,
    lack: Any,
) -> None:
    route = decision.recommended_route
    disposition = decision.disposition
    supported = (route == "rfa" and rfa.can_satisfy) or (route == "cm" and cm.can_satisfy)
    if route not in {"rfa", "cm", "clarification"} or (route in {"rfa", "cm"} and not supported):
        challenge(C.ROUTE_REVIEW_INCONSISTENT, F.CAPABILITY_REVIEWS, Q.RECONCILE_ROUTE_EVIDENCE)
    if not rfa.can_satisfy and not cm.can_satisfy:
        lack(M.ROUTE_REVIEW_SUPPORT, F.CAPABILITY_REVIEWS, Q.RECONCILE_ROUTE_EVIDENCE)
    selected_team = rfa.suggested_team_id if route == "rfa" else cm.suggested_collection_team_id
    valid_dispositions = {
        "auto_applied",
        "manager_review",
        "clarification",
        "shadow_recommendation",
    }
    invalid_pair = disposition not in valid_dispositions
    invalid_pair |= disposition == "auto_applied" and route == "clarification"
    invalid_pair |= disposition == "clarification" and route != "clarification"
    invalid_pair |= disposition == "auto_applied" and rfa.can_satisfy and cm.can_satisfy
    invalid_pair |= (
        disposition == "auto_applied" and capacity.get(selected_team or "") != "available"
    )
    if invalid_pair:
        challenge(C.DISPOSITION_ROUTE_INCONSISTENT, F.ROUTING_DECISION, Q.RECONCILE_ROUTE_EVIDENCE)
    if route in {"rfa", "cm"} and (not selected_team or selected_team not in capacity):
        lack(M.CANDIDATE_CAPACITY, F.CANDIDATE_CAPACITY, Q.VERIFY_CAPACITY_RECORDS)
    expected_evidence = _evidence_outcome(rfa, cm, disposition)
    if decision.evidence_outcome != expected_evidence:
        challenge(C.EVIDENCE_OUTCOME_INCONSISTENT, F.ROUTING_DECISION, Q.RECONCILE_ROUTE_EVIDENCE)
    expected_state = _expected_state(disposition, route)
    if _state_value(committed_state) != expected_state:
        challenge(C.COMMITTED_STATE_INCONSISTENT, F.COMMITTED_STATE, Q.RETURN_TO_JIOC_REVIEW)


def _expected_state(disposition: str, route: str) -> str:
    if disposition in {"manager_review", "shadow_recommendation"}:
        return TicketState.JIOC_REVIEW.value
    if disposition == "clarification" or route == "clarification":
        return TicketState.INFO_REQUIRED.value
    return (
        TicketState.COLLECT_CHOICE.value if route == "cm" else TicketState.ANALYST_ASSIGNMENT.value
    )


def _evidence_outcome(rfa: RfaCapabilityReview, cm: CmCapabilityReview, disposition: str) -> str:
    if rfa.can_satisfy and cm.can_satisfy:
        return "conflicting"
    if rfa.can_satisfy:
        return "eligible_rfa"
    if cm.can_satisfy:
        return "eligible_cm"
    return "clarification_required" if disposition == "clarification" else "insufficient_evidence"


def _has_open_offer(statuses: tuple[str, ...]) -> bool:
    return any(value.rsplit(":", 1)[-1].casefold() == "offered" for value in statuses)


def _state_value(state: TicketState | str) -> str:
    return state.value if isinstance(state, TicketState) else state


def _add(values: list[Any], value: Any) -> None:
    if value not in values:
        values.append(value)
