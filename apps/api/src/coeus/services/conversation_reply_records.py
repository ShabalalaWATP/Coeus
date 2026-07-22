"""Construct immutable records for deterministic and planner-backed intake replies."""

from hashlib import sha256

from coeus.domain.advisory_agents import AgentAdvice, AgentAdviceProvenance
from coeus.services.intake import AdmittedAssistantReply
from coeus.services.intake_planner_advice import intake_agent_advice


def deterministic_reply(text: str, outcome: str) -> AdmittedAssistantReply:
    return AdmittedAssistantReply(
        text,
        False,
        outcome=outcome,
        fallback_outcome="not_applicable",
        validation_outcome="deterministic",
        policy_version="intake-conversation-v1",
        context_schema_version="intake-details-v1",
    )


def text_hash(value: str) -> str:
    return f"sha256:{sha256(value.encode('utf-8')).hexdigest()}"


def advice_for_reply(reply: AdmittedAssistantReply) -> AgentAdvice | None:
    if reply.plan is None:
        return None
    provenance = AgentAdviceProvenance(
        provider_attempted=reply.duration_ms is not None,
        provider_succeeded=reply.outcome == "provider_success",
        outcome=reply.outcome,
        provider=reply.provider,
        model=reply.model,
        duration_ms=reply.duration_ms,
        fallback_outcome=reply.fallback_outcome or "not_applicable",
        validation_outcome=reply.validation_outcome or "not_run",
        prompt_version=reply.prompt_version or "intake-planner-v1",
        policy_version=reply.policy_version or "intake-planner-policy-v1",
        context_schema_version=reply.context_schema_version or "intake-extracted-fields-v1",
        input_hash=reply.input_hash,
        output_hash=reply.output_hash,
        input_token_count=reply.input_tokens,
        output_token_count=reply.output_tokens,
        error_class=reply.error_class,
    )
    return intake_agent_advice(reply.plan, provenance)
