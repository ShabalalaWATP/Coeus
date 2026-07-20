from collections.abc import Callable
from hashlib import sha256
from time import monotonic_ns

from coeus.application.ports.admission import ProviderAdmission
from coeus.application.ports.workflow_transaction import WorkflowTransactionPort
from coeus.core.config import HOSTED_ENVIRONMENTS, Settings
from coeus.core.errors import AppError
from coeus.core.logging import get_logger
from coeus.domain.tickets import IntakeDetails
from coeus.integrations.llm_gateway import LlmCall, LlmGeneration, generate_text
from coeus.persistence.state_store import StateStore
from coeus.repositories.tickets import InMemoryTicketRepository
from coeus.services.admission_metrics import AdmissionMetrics
from coeus.services.ai_models import AiModelService
from coeus.services.ai_provider_catalog import initial_api_keys, spec_for
from coeus.services.audit import AuditLog
from coeus.services.intake import (
    AdmittedAssistantReply,
    IntakeExtractionService,
    MockLlmProvider,
    RequirementCompletenessService,
)
from coeus.services.intake_prompt import (
    INTAKE_CONTEXT_SCHEMA_VERSION,
    INTAKE_POLICY_VERSION,
    INTAKE_PROMPT_VERSION,
    intake_prompt,
    validated_intake_reply,
)
from coeus.services.intake_provider_calls import PreparedIntakeReply
from coeus.services.postgres_provider_admission import PostgresProviderAdmissionController
from coeus.services.postgres_ticket_admission import PostgresTicketAdmissionController
from coeus.services.provider_admission import ProviderAdmissionController
from coeus.services.provider_circuit import ProviderCircuitBreaker
from coeus.services.ticket_admission import TicketAdmissionController
from coeus.services.ticket_conversations import ConversationService
from coeus.services.tickets import TicketService, TicketServices


def build_ticket_services(
    settings: Settings,
    audit_log: AuditLog,
    state_store: StateStore | None = None,
    ai_models: AiModelService | None = None,
    transaction: WorkflowTransactionPort | None = None,
    admission_metrics: AdmissionMetrics | None = None,
    provider_admission: ProviderAdmission | None = None,
) -> TicketServices:
    metrics = admission_metrics or AdmissionMetrics()
    repository = InMemoryTicketRepository(state_store)
    completeness = RequirementCompletenessService()
    tickets = TicketService(repository, completeness, audit_log, transaction)
    conversations = ConversationService(
        repository,
        tickets,
        tickets.mutations,
        IntakeExtractionService(),
        ConfigurableIntakeProvider(settings, ai_models),
        audit_log,
        provider_admission or build_provider_admission(settings, metrics),
        _ticket_admission(settings, repository, metrics),
    )
    return TicketServices(
        tickets=tickets,
        conversations=conversations,
        mutations=tickets.mutations,
    )


def build_provider_admission(
    settings: Settings,
    metrics: AdmissionMetrics,
) -> ProviderAdmissionController | PostgresProviderAdmissionController:
    if settings.environment in HOSTED_ENVIRONMENTS:
        return PostgresProviderAdmissionController(
            settings.database_url,
            max_concurrent=settings.provider_max_concurrent,
            max_calls_per_window=settings.provider_max_calls_per_window,
            max_calls_per_principal=settings.provider_max_calls_per_principal,
            window_seconds=settings.provider_window_seconds,
            mode=settings.provider_admission_mode,
            metrics=metrics,
        )
    return ProviderAdmissionController(
        max_concurrent=settings.provider_max_concurrent,
        max_calls_per_window=settings.provider_max_calls_per_window,
        max_calls_per_principal=settings.provider_max_calls_per_principal,
        window_seconds=settings.provider_window_seconds,
        mode=settings.provider_admission_mode,
        metrics=metrics,
    )


def _ticket_admission(
    settings: Settings, repository: InMemoryTicketRepository, metrics: AdmissionMetrics
) -> TicketAdmissionController | PostgresTicketAdmissionController:
    if settings.environment in HOSTED_ENVIRONMENTS:
        return PostgresTicketAdmissionController(
            settings.database_url,
            max_retained=settings.ticket_max_retained,
            max_retained_per_principal=settings.ticket_max_retained_per_principal,
            mode=settings.ticket_admission_mode,
            metrics=metrics,
        )
    return TicketAdmissionController(
        repository,
        max_retained=settings.ticket_max_retained,
        max_retained_per_principal=settings.ticket_max_retained_per_principal,
        mode=settings.ticket_admission_mode,
        metrics=metrics,
    )


class ConfigurableIntakeProvider:
    """Routes assistant replies to the configured provider with safe fallbacks.

    Flagged messages are answered with the fixed refusal locally so flagged
    text is never sent to any external API, and any provider failure degrades
    to the deterministic mock reply rather than losing the customer's message.
    """

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
        """Execute a prepared call for direct, already-admitted callers."""
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
                    policy_version=INTAKE_POLICY_VERSION,
                    context_schema_version=INTAKE_CONTEXT_SCHEMA_VERSION,
                )
            )
        remote = self._remote_call(intake)
        if remote is None:
            return _prepared_local(
                AdmittedAssistantReply(
                    self._mock.build_assistant_message(intake, safety_flags),
                    False,
                    outcome="local_provider",
                    fallback_outcome="not_applicable",
                    validation_outcome="deterministic",
                    policy_version=INTAKE_POLICY_VERSION,
                    context_schema_version=INTAKE_CONTEXT_SCHEMA_VERSION,
                )
            )
        call, requested_field = remote
        if not self._circuit.can_attempt():
            return _prepared_local(
                self._remote_fallback(
                    call,
                    intake,
                    safety_flags,
                    "circuit_open_fallback",
                    "ProviderCircuitOpen",
                )
            )
        unavailable = self._remote_fallback(
            call,
            intake,
            safety_flags,
            "provider_admission_unavailable_fallback",
            "ProviderAdmissionUnavailable",
        )
        return PreparedIntakeReply(
            True,
            unavailable,
            lambda: self._execute_remote(call, requested_field, intake, safety_flags),
        )

    def _execute_remote(
        self,
        call: LlmCall,
        requested_field: str,
        intake: IntakeDetails,
        safety_flags: tuple[str, ...],
    ) -> AdmittedAssistantReply:
        if not self._circuit.try_acquire():
            return self._remote_fallback(
                call,
                intake,
                safety_flags,
                "circuit_open_fallback",
                "ProviderCircuitOpen",
            )
        started_at = monotonic_ns()
        try:
            generated = self._text_generator(call)
        except AppError as error:
            self._circuit.record_failure()
            provider_completed = error.code == "llm_provider_invalid_response"
            self._logger.warning(
                "LLM provider unavailable; falling back to mock reply.",
                extra={"error_code": error.code, "provider": call.provider},
            )
            return AdmittedAssistantReply(
                self._mock.build_assistant_message(intake, safety_flags),
                provider_completed,
                provider=call.provider,
                model=call.model,
                duration_ms=_elapsed_ms(started_at),
                outcome=(
                    "invalid_output_fallback" if provider_completed else "provider_error_fallback"
                ),
                prompt_version=INTAKE_PROMPT_VERSION,
                fallback_outcome="deterministic",
                validation_outcome="failed" if provider_completed else "not_run",
                policy_version=INTAKE_POLICY_VERSION,
                context_schema_version=INTAKE_CONTEXT_SCHEMA_VERSION,
                input_hash=_call_hash(call),
                error_class=f"AppError:{error.code}",
            )
        except Exception:
            self._circuit.record_failure()
            raise
        raw = str(generated) if isinstance(generated, str) else ""
        text = validated_intake_reply(raw, requested_field)
        if text is None:
            self._circuit.record_failure()
        else:
            self._circuit.record_success()
        outcome = "provider_success" if text is not None else "invalid_output_fallback"
        return AdmittedAssistantReply(
            text or self._mock.build_assistant_message(intake, safety_flags),
            True,
            provider=call.provider,
            model=call.model,
            duration_ms=_elapsed_ms(started_at),
            outcome=outcome,
            prompt_version=INTAKE_PROMPT_VERSION,
            input_tokens=(generated.input_tokens if isinstance(generated, LlmGeneration) else None),
            output_tokens=(
                generated.output_tokens if isinstance(generated, LlmGeneration) else None
            ),
            fallback_outcome="not_used" if text is not None else "deterministic",
            validation_outcome="passed" if text is not None else "failed",
            policy_version=INTAKE_POLICY_VERSION,
            context_schema_version=INTAKE_CONTEXT_SCHEMA_VERSION,
            input_hash=_call_hash(call),
            output_hash=_text_hash(raw),
            error_class=None if text is not None else "ProviderOutputValidationError",
        )

    def _remote_fallback(
        self,
        call: LlmCall,
        intake: IntakeDetails,
        safety_flags: tuple[str, ...],
        outcome: str,
        error_class: str,
    ) -> AdmittedAssistantReply:
        return AdmittedAssistantReply(
            self._mock.build_assistant_message(intake, safety_flags),
            False,
            provider=call.provider,
            model=call.model,
            outcome=outcome,
            prompt_version=INTAKE_PROMPT_VERSION,
            fallback_outcome="deterministic",
            validation_outcome="not_run",
            policy_version=INTAKE_POLICY_VERSION,
            context_schema_version=INTAKE_CONTEXT_SCHEMA_VERSION,
            input_hash=_call_hash(call),
            error_class=error_class,
        )

    def _remote_call(self, intake: IntakeDetails) -> tuple[LlmCall, str] | None:
        # The configured provider is authoritative: an API key alone never
        # switches the provider, and a remote provider is only called when a
        # key is actually available.
        if self._ai_models is not None:
            provider = self._ai_models.provider()
            api_key = self._ai_models.api_key(provider)
            model = self._ai_models.active_model(provider) if provider != "mock" else ""
        else:
            provider = self._settings.llm_provider
            api_key = initial_api_keys(self._settings).get(provider)
            spec = spec_for(self._settings, provider)
            model = spec.default_model if spec else ""
        if provider == "mock" or not api_key:
            return None
        prompt = intake_prompt(intake, ())
        return (
            LlmCall(
                provider=provider,
                model=model,
                api_key=api_key,
                prompt=prompt.data,
                timeout=self._settings.llm_api_timeout_seconds,
                region=self._settings.bedrock_region,
                instructions=prompt.instructions,
                structured_output=True,
            ),
            prompt.requested_field,
        )


def _elapsed_ms(started_at: int) -> int:
    return max(0, (monotonic_ns() - started_at) // 1_000_000)


def _prepared_local(reply: AdmittedAssistantReply) -> PreparedIntakeReply:
    return PreparedIntakeReply(False, reply, lambda: reply)


def _call_hash(call: LlmCall) -> str:
    return _text_hash(f"{call.instructions}\n{call.prompt}")


def _text_hash(value: str) -> str:
    return f"sha256:{sha256(value.encode('utf-8')).hexdigest()}"
