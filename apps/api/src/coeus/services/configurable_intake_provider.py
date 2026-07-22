"""Configured intake-planner provider with deterministic controller fallback."""

from collections.abc import Callable
from hashlib import sha256
from time import monotonic_ns

from coeus.core.config import Settings
from coeus.core.errors import AppError
from coeus.core.logging import get_logger
from coeus.domain.advisory_agents import AdvisoryAgentKind, AdvisoryPrompt
from coeus.domain.tickets import IntakeDetails
from coeus.integrations.llm_gateway import LlmCall, LlmGeneration, generate_text
from coeus.services.advisory_provider_selection import (
    AdvisoryProviderSelection,
    freeze_advisory_provider,
)
from coeus.services.ai_models import AiModelService
from coeus.services.intake import AdmittedAssistantReply, MockLlmProvider
from coeus.services.intake_planner import (
    INTAKE_PLANNER_CONTEXT_SCHEMA_VERSION,
    INTAKE_PLANNER_POLICY_VERSION,
    INTAKE_PLANNER_PROMPT_VERSION,
    controller_intake_plan,
    deterministic_intake_plan,
    intake_planner_prompt,
    validated_intake_plan,
)
from coeus.services.intake_planner_advice import render_intake_plan
from coeus.services.intake_provider_calls import PreparedIntakeReply
from coeus.services.provider_circuit import ProviderCircuitBreaker


class ConfigurableIntakeProvider:
    """Produce bounded advice; application code retains wording and lifecycle authority."""

    def __init__(
        self,
        settings: Settings,
        ai_models: AiModelService | None,
        text_generator: Callable[[LlmCall], str] = generate_text,
    ) -> None:
        self._settings = settings
        self._ai_models = ai_models
        self._mock = MockLlmProvider()
        self._text_generator = text_generator
        self._circuit = ProviderCircuitBreaker(
            failure_threshold=settings.provider_circuit_failure_threshold,
            cooldown_seconds=settings.provider_circuit_cooldown_seconds,
        )
        self._logger = get_logger(__name__)

    def build_assistant_message(self, intake: IntakeDetails, safety_flags: tuple[str, ...]) -> str:
        return self.build_admitted_assistant_message(intake, safety_flags).text

    def build_admitted_assistant_message(
        self, intake: IntakeDetails, safety_flags: tuple[str, ...]
    ) -> AdmittedAssistantReply:
        return self.prepare_assistant_reply(intake, safety_flags).execute()

    def prepare_assistant_reply(
        self, intake: IntakeDetails, safety_flags: tuple[str, ...]
    ) -> PreparedIntakeReply:
        """Freeze provider selection and call data before admission is decided."""
        if safety_flags:
            return _prepared_local(
                AdmittedAssistantReply(
                    self._mock.build_assistant_message(intake, safety_flags),
                    False,
                    outcome="safety_refusal",
                    fallback_outcome="not_applicable",
                    validation_outcome="not_run",
                    policy_version=INTAKE_PLANNER_POLICY_VERSION,
                    context_schema_version=INTAKE_PLANNER_CONTEXT_SCHEMA_VERSION,
                )
            )
        plan = deterministic_intake_plan(intake, intake.missing_information)
        selection = self._remote_selection(intake)
        remote = selection.call
        if remote is None:
            if selection.unavailable_outcome is not None:
                return _prepared_local(self._selection_fallback(selection, intake))
            return _prepared_local(
                AdmittedAssistantReply(
                    render_intake_plan(plan, intake),
                    False,
                    outcome="local_provider",
                    fallback_outcome="not_applicable",
                    validation_outcome="deterministic",
                    policy_version=INTAKE_PLANNER_POLICY_VERSION,
                    context_schema_version=INTAKE_PLANNER_CONTEXT_SCHEMA_VERSION,
                    plan=plan,
                )
            )
        if not self._circuit.can_attempt():
            return _prepared_local(
                self._remote_fallback(
                    remote, intake, "circuit_open_fallback", "ProviderCircuitOpen"
                )
            )
        unavailable = self._remote_fallback(
            remote,
            intake,
            "provider_admission_unavailable_fallback",
            "ProviderAdmissionUnavailable",
        )
        return PreparedIntakeReply(
            True,
            unavailable,
            lambda: self._execute_remote(remote, intake),
        )

    def _execute_remote(self, call: LlmCall, intake: IntakeDetails) -> AdmittedAssistantReply:
        if not self._circuit.try_acquire():
            return self._remote_fallback(
                call, intake, "circuit_open_fallback", "ProviderCircuitOpen"
            )
        started_at = monotonic_ns()
        try:
            generated = self._text_generator(call)
        except AppError as error:
            self._circuit.record_failure()
            completed = error.code == "llm_provider_invalid_response"
            self._logger.warning(
                "LLM provider unavailable; falling back to local intake planning.",
                extra={"error_code": error.code, "provider": call.provider},
            )
            return self._failed_call_reply(
                call, intake, f"AppError:{error.code}", completed, started_at
            )
        except Exception as error:
            self._circuit.record_failure()
            self._logger.warning(
                "LLM provider failed unexpectedly; falling back to local intake planning.",
                extra={"error_class": type(error).__name__, "provider": call.provider},
            )
            return self._failed_call_reply(call, intake, type(error).__name__, False, started_at)
        raw = str(generated) if isinstance(generated, str) else ""
        proposed = validated_intake_plan(raw, intake.missing_information)
        plan = controller_intake_plan(intake, intake.missing_information, proposed)
        if proposed is None:
            self._circuit.record_failure()
        else:
            self._circuit.record_success()
        admitted = proposed is plan
        valid = proposed is not None
        return AdmittedAssistantReply(
            render_intake_plan(plan, intake),
            True,
            provider=call.provider,
            model=call.model,
            duration_ms=_elapsed_ms(started_at),
            outcome=(
                "provider_success"
                if admitted
                else "controller_override_fallback"
                if valid
                else "invalid_output_fallback"
            ),
            prompt_version=INTAKE_PLANNER_PROMPT_VERSION,
            input_tokens=generated.input_tokens if isinstance(generated, LlmGeneration) else None,
            output_tokens=(
                generated.output_tokens if isinstance(generated, LlmGeneration) else None
            ),
            fallback_outcome="not_used" if admitted else "deterministic",
            validation_outcome="passed" if valid else "failed",
            policy_version=INTAKE_PLANNER_POLICY_VERSION,
            context_schema_version=INTAKE_PLANNER_CONTEXT_SCHEMA_VERSION,
            input_hash=_call_hash(call),
            output_hash=_text_hash(raw),
            error_class=(
                None
                if admitted
                else "ControllerOverride"
                if valid
                else "ProviderOutputValidationError"
            ),
            plan=plan,
        )

    def _failed_call_reply(
        self,
        call: LlmCall,
        intake: IntakeDetails,
        error_class: str,
        completed: bool,
        started_at: int,
    ) -> AdmittedAssistantReply:
        plan = deterministic_intake_plan(intake, intake.missing_information)
        return AdmittedAssistantReply(
            render_intake_plan(plan, intake),
            completed,
            provider=call.provider,
            model=call.model,
            duration_ms=_elapsed_ms(started_at),
            outcome="invalid_output_fallback" if completed else "provider_error_fallback",
            prompt_version=INTAKE_PLANNER_PROMPT_VERSION,
            fallback_outcome="deterministic",
            validation_outcome="failed" if completed else "not_run",
            policy_version=INTAKE_PLANNER_POLICY_VERSION,
            context_schema_version=INTAKE_PLANNER_CONTEXT_SCHEMA_VERSION,
            input_hash=_call_hash(call),
            error_class=error_class,
            plan=plan,
        )

    def _remote_fallback(
        self, call: LlmCall, intake: IntakeDetails, outcome: str, error_class: str
    ) -> AdmittedAssistantReply:
        plan = deterministic_intake_plan(intake, intake.missing_information)
        return AdmittedAssistantReply(
            render_intake_plan(plan, intake),
            False,
            provider=call.provider,
            model=call.model,
            outcome=outcome,
            prompt_version=INTAKE_PLANNER_PROMPT_VERSION,
            fallback_outcome="deterministic",
            validation_outcome="not_run",
            policy_version=INTAKE_PLANNER_POLICY_VERSION,
            context_schema_version=INTAKE_PLANNER_CONTEXT_SCHEMA_VERSION,
            input_hash=_call_hash(call),
            error_class=error_class,
            plan=plan,
        )

    def _selection_fallback(
        self, selection: AdvisoryProviderSelection, intake: IntakeDetails
    ) -> AdmittedAssistantReply:
        plan = deterministic_intake_plan(intake, intake.missing_information)
        return AdmittedAssistantReply(
            render_intake_plan(plan, intake),
            False,
            provider=selection.provider,
            model=selection.model,
            outcome=selection.unavailable_outcome or "provider_not_configured_fallback",
            prompt_version=INTAKE_PLANNER_PROMPT_VERSION,
            fallback_outcome="deterministic",
            validation_outcome="not_run",
            policy_version=INTAKE_PLANNER_POLICY_VERSION,
            context_schema_version=INTAKE_PLANNER_CONTEXT_SCHEMA_VERSION,
            input_hash=selection.input_hash,
            error_class=selection.error_class or "ProviderNotConfigured",
            plan=plan,
        )

    def _remote_selection(self, intake: IntakeDetails) -> AdvisoryProviderSelection:
        prepared = intake_planner_prompt(intake, intake.missing_information)
        prompt = AdvisoryPrompt(
            data=prepared.data,
            instructions=prepared.instructions,
            prompt_version=INTAKE_PLANNER_PROMPT_VERSION,
            policy_version=INTAKE_PLANNER_POLICY_VERSION,
            context_schema_version=INTAKE_PLANNER_CONTEXT_SCHEMA_VERSION,
            max_output_tokens=256,
        )
        return freeze_advisory_provider(
            self._settings,
            self._ai_models,
            AdvisoryAgentKind.INTAKE_PLANNER,
            prompt,
        )


def _elapsed_ms(started_at: int) -> int:
    return max(0, (monotonic_ns() - started_at) // 1_000_000)


def _prepared_local(reply: AdmittedAssistantReply) -> PreparedIntakeReply:
    return PreparedIntakeReply(False, reply, lambda: reply)


def _call_hash(call: LlmCall) -> str:
    return _text_hash(f"{call.instructions}\n{call.prompt}")


def _text_hash(value: str) -> str:
    return f"sha256:{sha256(value.encode('utf-8')).hexdigest()}"
