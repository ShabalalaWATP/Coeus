"""Configured provider for one evidence-grounded intake interpretation."""

from collections.abc import Callable
from dataclasses import dataclass, field
from hashlib import sha256
from time import monotonic_ns

from coeus.core.config import Settings
from coeus.core.errors import AppError
from coeus.core.logging import get_logger
from coeus.domain.advisory_agents import AdvisoryAgentKind
from coeus.integrations.llm_gateway import LlmCall, LlmGeneration, generate_text
from coeus.services.advisory_provider_selection import freeze_advisory_provider
from coeus.services.ai_models import AiModelService
from coeus.services.intake_interpretation import (
    IntakeInterpretation,
    intake_interpretation_prompt,
    interpretation_answer_is_bounded,
    validate_intake_interpretation,
)
from coeus.services.provider_circuit import ProviderCircuitBreaker


@dataclass(frozen=True)
class AdmittedIntakeInterpretation:
    interpretation: IntakeInterpretation | None
    provider_succeeded: bool
    provider: str | None = None
    model: str | None = None
    duration_ms: int | None = None
    outcome: str = "interpretation_not_attempted"
    input_tokens: int | None = None
    output_tokens: int | None = None
    fallback_outcome: str = "deterministic"
    validation_outcome: str = "not_run"
    input_hash: str | None = None
    output_hash: str | None = None
    error_class: str | None = None


@dataclass(frozen=True)
class PreparedIntakeInterpretation:
    requires_admission: bool
    admission_unavailable_reply: AdmittedIntakeInterpretation
    _execute: Callable[[], AdmittedIntakeInterpretation] = field(repr=False, compare=False)

    def execute(self) -> AdmittedIntakeInterpretation:
        return self._execute()


class ConfigurableIntakeInterpreter:
    def __init__(
        self,
        settings: Settings,
        ai_models: AiModelService | None,
        circuit: ProviderCircuitBreaker,
        text_generator: Callable[[LlmCall], str] = generate_text,
    ) -> None:
        self._settings = settings
        self._ai_models = ai_models
        self._circuit = circuit
        self._text_generator = text_generator
        self._logger = get_logger(__name__)

    def prepare(
        self, current_answer: str, target_field: str
    ) -> PreparedIntakeInterpretation | None:
        if not interpretation_answer_is_bounded(current_answer):
            return None
        prompt = intake_interpretation_prompt(current_answer, target_field)
        selection = freeze_advisory_provider(
            self._settings,
            self._ai_models,
            AdvisoryAgentKind.INTAKE_PLANNER,
            prompt,
        )
        call = selection.call
        if call is None:
            return None
        if not self._circuit.can_attempt():
            fallback = self._fallback(
                call,
                "provider_interpretation_circuit_open",
                "ProviderCircuitOpen",
            )
            return PreparedIntakeInterpretation(False, fallback, lambda: fallback)
        unavailable = self._fallback(
            call,
            "provider_interpretation_admission_unavailable",
            "ProviderAdmissionUnavailable",
        )
        return PreparedIntakeInterpretation(
            True,
            unavailable,
            lambda: self._execute(call, current_answer, target_field),
        )

    def _execute(
        self, call: LlmCall, current_answer: str, target_field: str
    ) -> AdmittedIntakeInterpretation:
        if not self._circuit.try_acquire():
            return self._fallback(
                call,
                "provider_interpretation_circuit_open",
                "ProviderCircuitOpen",
            )
        started_at = monotonic_ns()
        try:
            generated = self._text_generator(call)
        except AppError as error:
            self._circuit.record_failure()
            completed = error.code == "llm_provider_invalid_response"
            self._logger.warning(
                "LLM interpretation unavailable; using deterministic intake.",
                extra={"error_code": error.code, "provider": call.provider},
            )
            return self._failed(
                call,
                f"AppError:{error.code}",
                completed,
                started_at,
            )
        except Exception as error:
            self._circuit.record_failure()
            self._logger.warning(
                "LLM interpretation failed unexpectedly; using deterministic intake.",
                extra={"error_class": type(error).__name__, "provider": call.provider},
            )
            return self._failed(call, type(error).__name__, False, started_at)
        raw = str(generated) if isinstance(generated, str) else ""
        validation = validate_intake_interpretation(raw, current_answer, target_field)
        proposal = validation.interpretation
        if validation.status == "failed":
            self._circuit.record_failure()
        else:
            self._circuit.record_success()
        abstained = validation.status == "abstained"
        return AdmittedIntakeInterpretation(
            proposal,
            True,
            provider=call.provider,
            model=call.model,
            duration_ms=_elapsed_ms(started_at),
            outcome=(
                "provider_interpretation_confirmation_requested"
                if proposal is not None
                else "provider_interpretation_abstained"
                if abstained
                else "provider_interpretation_invalid_output"
            ),
            input_tokens=(generated.input_tokens if isinstance(generated, LlmGeneration) else None),
            output_tokens=(
                generated.output_tokens if isinstance(generated, LlmGeneration) else None
            ),
            fallback_outcome="not_used" if proposal is not None else "deterministic",
            validation_outcome=validation.status,
            input_hash=_call_hash(call),
            output_hash=_text_hash(raw),
            error_class=(
                None if proposal is not None or abstained else "ProviderOutputValidationError"
            ),
        )

    def _failed(
        self,
        call: LlmCall,
        error_class: str,
        completed: bool,
        started_at: int,
    ) -> AdmittedIntakeInterpretation:
        return AdmittedIntakeInterpretation(
            None,
            completed,
            provider=call.provider,
            model=call.model,
            duration_ms=_elapsed_ms(started_at),
            outcome=(
                "provider_interpretation_invalid_output"
                if completed
                else "provider_interpretation_error_fallback"
            ),
            validation_outcome="failed" if completed else "not_run",
            input_hash=_call_hash(call),
            error_class=error_class,
        )

    @staticmethod
    def _fallback(call: LlmCall, outcome: str, error_class: str) -> AdmittedIntakeInterpretation:
        return AdmittedIntakeInterpretation(
            None,
            False,
            provider=call.provider,
            model=call.model,
            outcome=outcome,
            input_hash=_call_hash(call),
            error_class=error_class,
        )


def _elapsed_ms(started_at: int) -> int:
    return max(0, (monotonic_ns() - started_at) // 1_000_000)


def _call_hash(call: LlmCall) -> str:
    return _text_hash(f"{call.instructions}\n{call.prompt}")


def _text_hash(value: str) -> str:
    return f"sha256:{sha256(value.encode('utf-8')).hexdigest()}"
