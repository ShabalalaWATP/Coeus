"""Apply admitted interpretation and attach content-free run provenance."""

from dataclasses import replace

from coeus.domain.tickets import ChatMessage, IntakeDetails
from coeus.services.intake import AdmittedAssistantReply
from coeus.services.intake_confirmation import confirmation_prompt
from coeus.services.intake_interpretation import (
    INTAKE_INTERPRETATION_CONTEXT_SCHEMA_VERSION,
    INTAKE_INTERPRETATION_POLICY_VERSION,
    INTAKE_INTERPRETATION_PROMPT_VERSION,
)
from coeus.services.intake_interpretation_provider import AdmittedIntakeInterpretation
from coeus.services.intake_planner import deterministic_intake_plan
from coeus.services.intake_retry import non_repeating_intake_reply


def reply_with_interpretation_provenance(
    reply: AdmittedAssistantReply,
    intake: IntakeDetails,
    outcome: AdmittedIntakeInterpretation | None,
) -> AdmittedAssistantReply:
    if outcome is None:
        return reply
    plan = deterministic_intake_plan(intake, intake.missing_information)
    return replace(
        reply,
        provider_succeeded=outcome.provider_succeeded,
        provider=outcome.provider,
        model=outcome.model,
        duration_ms=outcome.duration_ms,
        outcome=outcome.outcome,
        prompt_version=INTAKE_INTERPRETATION_PROMPT_VERSION,
        input_tokens=outcome.input_tokens,
        output_tokens=outcome.output_tokens,
        fallback_outcome=outcome.fallback_outcome,
        validation_outcome=outcome.validation_outcome,
        policy_version=INTAKE_INTERPRETATION_POLICY_VERSION,
        context_schema_version=INTAKE_INTERPRETATION_CONTEXT_SCHEMA_VERSION,
        input_hash=outcome.input_hash,
        output_hash=outcome.output_hash,
        error_class=outcome.error_class,
        plan=plan,
    )


def finalise_interpreted_reply(
    reply: AdmittedAssistantReply,
    messages: tuple[ChatMessage, ...],
    intake: IntakeDetails,
    outcome: AdmittedIntakeInterpretation | None,
) -> AdmittedAssistantReply:
    lifecycle_outcome = reply.outcome in {
        "close_refused_intake_contradiction",
        "close_refused_missing_information",
        "conversation_closed",
        "close_offered",
    }
    recorded = reply_with_interpretation_provenance(reply, intake, outcome)
    if lifecycle_outcome:
        return recorded
    if outcome is not None and outcome.interpretation is not None:
        return replace(recorded, text=confirmation_prompt(outcome.interpretation))
    return replace(
        recorded,
        text=non_repeating_intake_reply(messages, intake, recorded.text),
    )
