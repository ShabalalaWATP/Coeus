from datetime import UTC, datetime
from uuid import uuid4

from coeus.schemas.tickets import AgentRunResponse


def test_agent_run_response_serialises_safe_provenance_aliases() -> None:
    response = AgentRunResponse(
        run_id=uuid4(),
        agent_name="customer-chatbot-agent",
        status="completed",
        summary="Provider response validated.",
        safety_flags=[],
        created_at=datetime.now(UTC),
        execution_kind="provider_backed",
        provider="synthetic-provider",
        model="synthetic-chat-model",
        duration_ms=125,
        fallback_outcome="not_used",
        validation_outcome="passed",
        prompt_version="intake-v2",
        policy_version="agent-boundaries-v1",
        context_schema_version="intake-context-v2",
        input_hash="sha256:" + "a" * 64,
        output_hash="sha256:" + "b" * 64,
        input_token_count=42,
        output_token_count=17,
        error_class=None,
    )

    payload = response.model_dump(by_alias=True)

    assert payload["executionKind"] == "provider_backed"
    assert payload["durationMs"] == 125
    assert payload["fallbackOutcome"] == "not_used"
    assert payload["validationOutcome"] == "passed"
    assert payload["promptVersion"] == "intake-v2"
    assert payload["policyVersion"] == "agent-boundaries-v1"
    assert payload["contextSchemaVersion"] == "intake-context-v2"
    assert payload["inputHash"].startswith("sha256:")
    assert payload["outputHash"].startswith("sha256:")
    assert payload["inputTokenCount"] == 42
    assert payload["outputTokenCount"] == 17
    assert "prompt" not in payload
    assert "output" not in payload
