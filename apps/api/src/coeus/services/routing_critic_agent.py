"""Provider-backed, shadow-only critic around the pure routing checks."""

from dataclasses import replace
from uuid import UUID

from coeus.domain.advisory_agents import (
    AdviceItemKind,
    AdvisoryAgentKind,
    AdvisoryPrompt,
    AgentAdvice,
    AgentAdviceItem,
)
from coeus.domain.enums import TicketState
from coeus.domain.jioc_routing import JiocRoutingContext, JiocRoutingDecision
from coeus.domain.routing_critic import (
    RoutingCriticSeverity,
    RoutingCriticVerdict,
    RoutingCritiqueDraft,
)
from coeus.domain.tickets import CmCapabilityReview, RfaCapabilityReview, TicketRecord
from coeus.services.bounded_advisory import BoundedAdvisoryService
from coeus.services.routing_critic import (
    ROUTING_CRITIC_PROMPT_VERSION,
    ROUTING_CRITIC_VERSION,
    critique_routing,
    parse_model_critique,
    routing_critic_prompt,
)


class RoutingCriticAgent:
    def __init__(self, advisory: BoundedAdvisoryService) -> None:
        self._advisory = advisory

    def critique(self, requester_id: UUID, ticket: TicketRecord) -> AgentAdvice:
        return self.critique_case(
            requester_id,
            ticket.jioc_routing_contexts[-1],
            ticket.jioc_routing_decisions[-1],
            ticket.rfa_reviews[-1],
            ticket.cm_reviews[-1],
            ticket.state,
        )

    def critique_case(
        self,
        requester_id: UUID,
        context: JiocRoutingContext,
        decision: JiocRoutingDecision,
        rfa: RfaCapabilityReview,
        cm: CmCapabilityReview,
        committed_state: TicketState,
    ) -> AgentAdvice:
        deterministic = critique_routing(context, decision, rfa, cm, committed_state)
        combined = routing_critic_prompt(context, decision, rfa, cm, committed_state)
        instructions, data = combined.split("\nFacts:", maxsplit=1)
        prompt = AdvisoryPrompt(
            data=data,
            instructions=instructions,
            prompt_version=ROUTING_CRITIC_PROMPT_VERSION,
            policy_version=ROUTING_CRITIC_VERSION,
            context_schema_version=context.schema_version,
            max_output_tokens=512,
        )
        admitted_drafts: list[RoutingCritiqueDraft] = []

        def parse(raw: str) -> tuple[AgentAdviceItem, ...]:
            provider = parse_model_critique(raw)
            if provider is None:
                raise ValueError("routing critic output failed validation")
            merged = _merge_critique(deterministic, provider)
            admitted_drafts.append(merged)
            return _critique_items(merged)

        record = self._advisory.advise(
            agent=AdvisoryAgentKind.ROUTING_CRITIC,
            requester_id=requester_id,
            prompt=prompt,
            fallback_items=_critique_items(deterministic),
            parser=parse,
        )
        admitted = admitted_drafts[-1] if admitted_drafts else deterministic
        return replace(
            record,
            verdict=admitted.verdict.value,
            shadow_only=True,
            context_references=(
                f"context:{context.context_id}",
                f"decision:{decision.decision_id}",
                f"requirement:{context.requirement_revision}",
            ),
        )


def _merge_critique(
    deterministic: RoutingCritiqueDraft, provider: RoutingCritiqueDraft
) -> RoutingCritiqueDraft:
    challenges = tuple(dict.fromkeys((*deterministic.challenge_codes, *provider.challenge_codes)))
    missing = tuple(
        dict.fromkeys((*deterministic.missing_evidence_codes, *provider.missing_evidence_codes))
    )
    facts = tuple(dict.fromkeys((*deterministic.cited_fact_ids, *provider.cited_fact_ids)))
    questions = tuple(
        dict.fromkeys((*deterministic.review_question_codes, *provider.review_question_codes))
    )
    verdict = (
        RoutingCriticVerdict.CHALLENGES
        if challenges
        else RoutingCriticVerdict.INSUFFICIENT_EVIDENCE
        if missing
        else RoutingCriticVerdict.SUPPORTS
    )
    severity = max(
        (deterministic.severity, provider.severity),
        key=lambda value: {
            RoutingCriticSeverity.INFO: 0,
            RoutingCriticSeverity.WARNING: 1,
            RoutingCriticSeverity.HIGH: 2,
        }[value],
    )
    return RoutingCritiqueDraft(verdict, severity, challenges, missing, facts, questions)


def _critique_items(draft: RoutingCritiqueDraft) -> tuple[AgentAdviceItem, ...]:
    references = tuple(value.value for value in draft.cited_fact_ids[:8])
    items = [
        AgentAdviceItem(
            AdviceItemKind.ROUTE_CHALLENGE,
            code.value,
            _label(code.value),
            references,
        )
        for code in draft.challenge_codes
    ]
    items.extend(
        AgentAdviceItem(
            AdviceItemKind.MISSING_EVIDENCE,
            code.value,
            _label(code.value),
            references,
        )
        for code in draft.missing_evidence_codes
    )
    items.extend(
        AgentAdviceItem(
            AdviceItemKind.REVIEW_QUESTION,
            code.value,
            _label(code.value),
            references,
        )
        for code in draft.review_question_codes
    )
    return tuple(items)


def _label(code: str) -> str:
    return code.replace("_", " ").capitalize() + "."
