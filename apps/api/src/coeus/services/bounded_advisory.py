"""Provider execution boundary for bounded, non-authoritative agent advice."""

from collections.abc import Callable
from hashlib import sha256
from time import monotonic_ns
from uuid import UUID

from coeus.application.ports.admission import ProviderAdmission
from coeus.core.config import Settings
from coeus.core.errors import AppError
from coeus.domain.advisory_agents import (
    AdvisoryAgentKind,
    AdvisoryPrompt,
    AgentAdvice,
    AgentAdviceItem,
    AgentAdviceProvenance,
    validate_advice_items,
)
from coeus.integrations.llm_gateway import LlmCall, LlmGeneration, generate_text
from coeus.services.advisory_provider_selection import freeze_advisory_provider
from coeus.services.ai_models import AiModelService
from coeus.services.provider_circuit import ProviderCircuitBreaker

AdviceParser = Callable[[str], tuple[AgentAdviceItem, ...]]
TextGenerator = Callable[[LlmCall], str]


class BoundedAdvisoryService:
    """Run optional provider reasoning without granting it action authority."""

    def __init__(
        self,
        settings: Settings,
        ai_models: AiModelService | None,
        provider_admission: ProviderAdmission,
        text_generator: TextGenerator = generate_text,
    ) -> None:
        self._settings = settings
        self._ai_models = ai_models
        self._provider_admission = provider_admission
        self._text_generator = text_generator
        self._circuit = ProviderCircuitBreaker(
            failure_threshold=settings.provider_circuit_failure_threshold,
            cooldown_seconds=settings.provider_circuit_cooldown_seconds,
        )

    def advise(
        self,
        *,
        agent: AdvisoryAgentKind,
        requester_id: UUID,
        prompt: AdvisoryPrompt,
        fallback_items: tuple[AgentAdviceItem, ...],
        parser: AdviceParser,
    ) -> AgentAdvice:
        """Return validated advice, falling back locally on every runtime failure."""
        validate_advice_items(agent, fallback_items)
        selection = freeze_advisory_provider(self._settings, self._ai_models, agent, prompt)
        if selection.call is None:
            error_class = selection.error_class or (
                "ProviderNotConfigured" if selection.provider != "mock" else None
            )
            return self._fallback(
                agent,
                fallback_items,
                prompt,
                provider=selection.provider,
                model=selection.model,
                outcome=(
                    selection.unavailable_outcome
                    or ("provider_not_configured_fallback" if error_class else "local_provider")
                ),
                fallback_outcome="deterministic" if error_class else "not_applicable",
                validation_outcome="not_run" if error_class else "deterministic",
                duration_ms=None,
                input_hash=selection.input_hash,
                error_class=error_class,
            )
        call = selection.call
        if not self._circuit.can_attempt():
            return self._remote_fallback(
                agent,
                fallback_items,
                prompt,
                call,
                outcome="circuit_open_fallback",
                error_class="ProviderCircuitOpen",
            )
        try:
            with self._provider_admission.reserve(requester_id) as reservation:
                if not self._circuit.try_acquire():
                    return self._remote_fallback(
                        agent,
                        fallback_items,
                        prompt,
                        call,
                        outcome="circuit_open_fallback",
                        error_class="ProviderCircuitOpen",
                    )
                started_at = monotonic_ns()
                try:
                    generated = self._text_generator(call)
                    reservation.commit()
                except Exception as error:
                    provider_completed = (
                        isinstance(error, AppError)
                        and error.code == "llm_provider_invalid_response"
                    )
                    if provider_completed:
                        reservation.commit()
                    self._circuit.record_failure()
                    return self._remote_fallback(
                        agent,
                        fallback_items,
                        prompt,
                        call,
                        outcome=(
                            "invalid_output_fallback"
                            if provider_completed
                            else "provider_error_fallback"
                        ),
                        error_class=_error_class(error),
                        provider_attempted=True,
                        duration_ms=_elapsed_ms(started_at),
                        validation_outcome="failed" if provider_completed else "not_run",
                    )
                raw = str(generated) if isinstance(generated, str) else ""
                try:
                    items = parser(raw)
                    validate_advice_items(agent, items)
                except Exception as error:
                    self._circuit.record_failure()
                    return self._remote_fallback(
                        agent,
                        fallback_items,
                        prompt,
                        call,
                        outcome="invalid_output_fallback",
                        error_class=_error_class(error, parser_failure=True),
                        provider_attempted=True,
                        duration_ms=_elapsed_ms(started_at),
                        output_hash=_text_hash(raw),
                        validation_outcome="failed",
                        generated=generated,
                    )
                self._circuit.record_success()
                return AgentAdvice(
                    agent=agent,
                    items=items,
                    shadow_only=agent is AdvisoryAgentKind.ROUTING_CRITIC,
                    provenance=self._provenance(
                        prompt,
                        provider_attempted=True,
                        provider_succeeded=True,
                        outcome="provider_success",
                        provider=call.provider,
                        model=call.model,
                        duration_ms=_elapsed_ms(started_at),
                        fallback_outcome="not_used",
                        validation_outcome="passed",
                        input_hash=_call_hash(call),
                        output_hash=_text_hash(raw),
                        generated=generated,
                    ),
                )
        except Exception as error:
            return self._remote_fallback(
                agent,
                fallback_items,
                prompt,
                call,
                outcome="provider_admission_unavailable_fallback",
                error_class=_error_class(error, admission_failure=True),
            )

    def _remote_fallback(
        self,
        agent: AdvisoryAgentKind,
        items: tuple[AgentAdviceItem, ...],
        prompt: AdvisoryPrompt,
        call: LlmCall,
        *,
        outcome: str,
        error_class: str,
        provider_attempted: bool = False,
        duration_ms: int | None = None,
        output_hash: str | None = None,
        validation_outcome: str = "not_run",
        generated: str | None = None,
    ) -> AgentAdvice:
        return self._fallback(
            agent,
            items,
            prompt,
            provider=call.provider,
            model=call.model,
            outcome=outcome,
            fallback_outcome="deterministic",
            validation_outcome=validation_outcome,
            input_hash=_call_hash(call),
            output_hash=output_hash,
            error_class=error_class,
            provider_attempted=provider_attempted,
            duration_ms=duration_ms,
            generated=generated,
        )

    def _fallback(
        self,
        agent: AdvisoryAgentKind,
        items: tuple[AgentAdviceItem, ...],
        prompt: AdvisoryPrompt,
        *,
        provider: str | None,
        model: str | None,
        outcome: str,
        fallback_outcome: str,
        validation_outcome: str,
        input_hash: str | None,
        duration_ms: int | None,
        error_class: str | None,
        provider_attempted: bool = False,
        output_hash: str | None = None,
        generated: str | None = None,
    ) -> AgentAdvice:
        return AgentAdvice(
            agent=agent,
            items=items,
            shadow_only=agent is AdvisoryAgentKind.ROUTING_CRITIC,
            provenance=self._provenance(
                prompt,
                provider=provider,
                model=model,
                outcome=outcome,
                fallback_outcome=fallback_outcome,
                validation_outcome=validation_outcome,
                input_hash=input_hash,
                duration_ms=duration_ms,
                error_class=error_class,
                provider_attempted=provider_attempted,
                output_hash=output_hash,
                generated=generated,
                provider_succeeded=False,
            ),
        )

    @staticmethod
    def _provenance(
        prompt: AdvisoryPrompt,
        *,
        provider_attempted: bool = False,
        provider_succeeded: bool,
        outcome: str,
        provider: str | None,
        model: str | None,
        duration_ms: int | None,
        fallback_outcome: str,
        validation_outcome: str,
        input_hash: str | None,
        output_hash: str | None = None,
        error_class: str | None = None,
        generated: str | None = None,
    ) -> AgentAdviceProvenance:
        return AgentAdviceProvenance(
            provider_attempted=provider_attempted,
            provider_succeeded=provider_succeeded,
            outcome=outcome,
            provider=provider,
            model=model,
            duration_ms=duration_ms,
            fallback_outcome=fallback_outcome,
            validation_outcome=validation_outcome,
            prompt_version=prompt.prompt_version,
            policy_version=prompt.policy_version,
            context_schema_version=prompt.context_schema_version,
            input_hash=input_hash,
            output_hash=output_hash,
            input_token_count=(
                generated.input_tokens if isinstance(generated, LlmGeneration) else None
            ),
            output_token_count=(
                generated.output_tokens if isinstance(generated, LlmGeneration) else None
            ),
            error_class=error_class,
        )


def _elapsed_ms(started_at: int) -> int:
    return max(0, (monotonic_ns() - started_at) // 1_000_000)


def _call_hash(call: LlmCall) -> str:
    return _text_hash(f"{call.instructions}\n{call.prompt}")


def _text_hash(value: str) -> str:
    return f"sha256:{sha256(value.encode('utf-8')).hexdigest()}"


def _error_class(
    error: Exception, *, parser_failure: bool = False, admission_failure: bool = False
) -> str:
    if parser_failure:
        return "ProviderOutputValidationError"
    if admission_failure:
        return "ProviderAdmissionUnavailable"
    if isinstance(error, AppError):
        return f"AppError:{error.code}"
    return type(error).__name__
