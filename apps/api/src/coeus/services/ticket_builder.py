from coeus.application.ports.workflow_transaction import WorkflowTransactionPort
from coeus.core.config import HOSTED_ENVIRONMENTS, Settings
from coeus.core.errors import AppError
from coeus.core.logging import get_logger
from coeus.domain.tickets import IntakeDetails
from coeus.integrations.llm_gateway import LlmCall, generate_text
from coeus.persistence.state_store import StateStore
from coeus.repositories.tickets import InMemoryTicketRepository
from coeus.services.ai_models import AiModelService
from coeus.services.ai_provider_catalog import initial_api_keys, spec_for
from coeus.services.audit import AuditLog
from coeus.services.intake import (
    IntakeExtractionService,
    MockLlmProvider,
    RequirementCompletenessService,
)
from coeus.services.intake_prompt import intake_prompt
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
) -> TicketServices:
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
        _provider_admission(settings),
        _ticket_admission(settings, repository),
    )
    return TicketServices(
        tickets=tickets,
        conversations=conversations,
        mutations=tickets.mutations,
    )


def _provider_admission(
    settings: Settings,
) -> ProviderAdmissionController | PostgresProviderAdmissionController:
    if settings.environment in HOSTED_ENVIRONMENTS:
        return PostgresProviderAdmissionController(
            settings.database_url,
            max_concurrent=settings.provider_max_concurrent,
            max_calls_per_window=settings.provider_max_calls_per_window,
            max_calls_per_principal=settings.provider_max_calls_per_principal,
            window_seconds=settings.provider_window_seconds,
            mode=settings.provider_admission_mode,
        )
    return ProviderAdmissionController(
        max_concurrent=settings.provider_max_concurrent,
        max_calls_per_window=settings.provider_max_calls_per_window,
        max_calls_per_principal=settings.provider_max_calls_per_principal,
        window_seconds=settings.provider_window_seconds,
        mode=settings.provider_admission_mode,
    )


def _ticket_admission(
    settings: Settings, repository: InMemoryTicketRepository
) -> TicketAdmissionController | PostgresTicketAdmissionController:
    if settings.environment in HOSTED_ENVIRONMENTS:
        return PostgresTicketAdmissionController(
            settings.database_url,
            max_retained=settings.ticket_max_retained,
            max_retained_per_principal=settings.ticket_max_retained_per_principal,
            mode=settings.ticket_admission_mode,
        )
    return TicketAdmissionController(
        repository,
        max_retained=settings.ticket_max_retained,
        max_retained_per_principal=settings.ticket_max_retained_per_principal,
        mode=settings.ticket_admission_mode,
    )


class ConfigurableIntakeProvider:
    """Routes assistant replies to the configured provider with safe fallbacks.

    Flagged messages are answered with the fixed refusal locally so flagged
    text is never sent to any external API, and any provider failure degrades
    to the deterministic mock reply rather than losing the customer's message.
    """

    def __init__(self, settings: Settings, ai_models: AiModelService | None) -> None:
        self._settings = settings
        self._ai_models = ai_models
        self._mock = MockLlmProvider()
        self._circuit = ProviderCircuitBreaker(
            failure_threshold=settings.provider_circuit_failure_threshold,
            cooldown_seconds=settings.provider_circuit_cooldown_seconds,
        )
        self._logger = get_logger(__name__)

    def build_assistant_message(self, intake: IntakeDetails, safety_flags: tuple[str, ...]) -> str:
        if safety_flags:
            return self._mock.build_assistant_message(intake, safety_flags)
        call = self._remote_call(intake)
        if call is None or not self._circuit.try_acquire():
            return self._mock.build_assistant_message(intake, safety_flags)
        try:
            text = generate_text(call)
        except AppError as error:
            self._circuit.record_failure()
            self._logger.warning(
                "LLM provider unavailable; falling back to mock reply.",
                extra={"error_code": error.code, "provider": call.provider},
            )
            return self._mock.build_assistant_message(intake, safety_flags)
        except Exception:
            self._circuit.record_failure()
            raise
        self._circuit.record_success()
        return text or self._mock.build_assistant_message(intake, safety_flags)

    def uses_operator_provider(self) -> bool:
        """Whether the next unflagged reply can acquire an external provider."""
        return self._circuit.can_attempt() and self._remote_call(IntakeDetails()) is not None

    def _remote_call(self, intake: IntakeDetails) -> LlmCall | None:
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
        return LlmCall(
            provider=provider,
            model=model,
            api_key=api_key,
            prompt=intake_prompt(intake, ()),
            timeout=self._settings.llm_api_timeout_seconds,
            region=self._settings.bedrock_region,
        )
