"""Persist admitted advisory output through the standard agent-run envelope."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from coeus.domain.advisory_agents import AgentAdvice
from coeus.domain.tickets import AgentExecutionKind, AgentRun, AgentRunStatus


def advisory_agent_run(
    ticket_id: UUID,
    agent_name: str,
    summary: str,
    advice: AgentAdvice,
    *,
    created_at: datetime | None = None,
) -> AgentRun:
    provenance = advice.provenance
    return AgentRun(
        run_id=uuid4(),
        ticket_id=ticket_id,
        agent_name=agent_name,
        status=AgentRunStatus.COMPLETED,
        summary=summary,
        safety_flags=(),
        created_at=created_at or datetime.now(UTC),
        execution_kind=(
            AgentExecutionKind.PROVIDER_BACKED
            if provenance.provider_attempted
            else AgentExecutionKind.DETERMINISTIC
        ),
        provider=provenance.provider,
        model=provenance.model,
        duration_ms=provenance.duration_ms,
        fallback_outcome=provenance.fallback_outcome,
        validation_outcome=provenance.validation_outcome,
        prompt_version=provenance.prompt_version,
        policy_version=provenance.policy_version,
        context_schema_version=provenance.context_schema_version,
        input_hash=provenance.input_hash,
        output_hash=provenance.output_hash,
        input_token_count=provenance.input_token_count,
        output_token_count=provenance.output_token_count,
        error_class=provenance.error_class,
        advice=advice,
    )
