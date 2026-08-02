"""Coordinate deterministic extraction and optional current-answer interpretation."""

from dataclasses import dataclass
from uuid import UUID

from coeus.application.ports.admission import ProviderAdmission
from coeus.domain.tickets import ChatMessage, IntakeDetails
from coeus.services import conversation_lifecycle as lifecycle
from coeus.services.intake import (
    IntakeAssistantProvider,
    IntakeExtractionService,
    RequirementCompletenessService,
)
from coeus.services.intake_confirmation import (
    confirmation_decision,
    confirmation_prompt,
    pending_confirmation,
)
from coeus.services.intake_interpretation import (
    active_intake_field,
    apply_interpretation,
    clarification_target,
    interpretation_target,
)
from coeus.services.intake_interpretation_provider import AdmittedIntakeInterpretation
from coeus.services.intake_provider_execution import execute_intake_interpretation
from coeus.services.intake_transcripts import (
    VoiceTurn,
    requester_message,
    voice_answers,
    voice_turns,
)


@dataclass(frozen=True)
class InterpretedIntakeTurn:
    customer_answer: str
    intake: IntakeDetails
    provider_outcome: AdmittedIntakeInterpretation | None
    allow_provider_reply: bool = True
    reply_override: str | None = None


def interpret_intake_turn(
    actor_user_id: UUID,
    raw_message: str,
    existing: IntakeDetails,
    messages: tuple[ChatMessage, ...],
    extractor: IntakeExtractionService,
    provider: IntakeAssistantProvider,
    admission: ProviderAdmission | None,
) -> InterpretedIntakeTurn:
    customer_answer = requester_message(raw_message)
    turns = voice_turns(raw_message)
    pending = pending_confirmation(messages)
    if pending is not None:
        decision_answer = (
            next(
                (turn.text for turn in reversed(turns) if turn.speaker == "user"),
                "",
            )
            if turns is not None
            else customer_answer
        )
        decision = confirmation_decision(decision_answer)
        if active_intake_field(existing) != pending.interpretation.target_field:
            if decision is not None:
                return InterpretedIntakeTurn(customer_answer, existing, None, False)
        else:
            if decision is True:
                updated = apply_interpretation(existing, pending.interpretation)
                complete = RequirementCompletenessService().with_completeness(updated)
                return InterpretedIntakeTurn(customer_answer, complete, None, False)
            if decision is False:
                return InterpretedIntakeTurn(customer_answer, existing, None, False)
            return InterpretedIntakeTurn(
                customer_answer,
                existing,
                None,
                False,
                confirmation_prompt(pending.interpretation),
            )
    if turns is None and lifecycle.wants_to_end(customer_answer):
        return InterpretedIntakeTurn(customer_answer, existing, None, False)
    prior_target = clarification_target(existing)
    intake = (
        extractor.extract_for_field(customer_answer, existing, prior_target)
        if prior_target is not None and turns is None
        else extractor.extract(raw_message, existing)
    )
    if prior_target is not None and turns is not None:
        clarification_answer = _target_answer(turns, prior_target)
        if clarification_answer and not lifecycle.wants_to_end(clarification_answer):
            intake = extractor.extract_for_field(clarification_answer, intake, prior_target)
    if lifecycle.wants_to_end(customer_answer):
        return InterpretedIntakeTurn(customer_answer, intake, None, False)
    target = interpretation_target(existing, intake, prior_target)
    interpretation_answer = (
        _target_answer(turns, target)
        if turns is not None and target is not None
        else customer_answer
    )
    outcome = (
        execute_intake_interpretation(
            actor_user_id,
            provider,
            admission,
            interpretation_answer,
            target,
        )
        if target is not None and interpretation_answer
        else None
    )
    return InterpretedIntakeTurn(
        customer_answer,
        intake,
        outcome,
        outcome is None,
    )


def _target_answer(turns: tuple[VoiceTurn, ...], target: str) -> str | None:
    answers = voice_answers(turns)
    return next((answer.text for answer in reversed(answers) if answer.field == target), None)
