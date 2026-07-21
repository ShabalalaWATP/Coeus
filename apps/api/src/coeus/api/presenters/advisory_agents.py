"""Render admitted advice without exposing prompt or raw provider material."""

from coeus.domain.advisory_agents import AgentAdvice
from coeus.schemas.advisory_agents import AgentAdviceItemResponse, AgentAdviceResponse


def advice_response(advice: AgentAdvice) -> AgentAdviceResponse:
    return AgentAdviceResponse(
        agent=advice.agent.value,
        outcome=advice.provenance.outcome,
        verdict=advice.verdict,
        shadow_only=advice.shadow_only,
        context_references=list(advice.context_references),
        provider_attempted=advice.provenance.provider_attempted,
        items=[
            AgentAdviceItemResponse(
                kind=item.kind.value,
                code=item.code,
                detail=item.detail,
                references=list(item.references),
            )
            for item in advice.items
        ],
    )
