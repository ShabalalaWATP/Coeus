from coeus.core.config import Settings
from coeus.core.errors import AppError
from coeus.core.logging import get_logger
from coeus.domain.tickets import IntakeDetails
from coeus.integrations.gemini_api import GeminiApiLlmProvider
from coeus.persistence.state_store import StateStore
from coeus.repositories.tickets import InMemoryTicketRepository
from coeus.services.ai_models import AiModelService
from coeus.services.audit import AuditLog
from coeus.services.intake import (
    IntakeExtractionService,
    MockLlmProvider,
    RequirementCompletenessService,
)
from coeus.services.ticket_conversations import ConversationService
from coeus.services.tickets import TicketService, TicketServices


def build_ticket_services(
    settings: Settings,
    audit_log: AuditLog,
    state_store: StateStore | None = None,
    ai_models: AiModelService | None = None,
) -> TicketServices:
    repository = InMemoryTicketRepository(state_store)
    completeness = RequirementCompletenessService()
    tickets = TicketService(repository, completeness, audit_log)
    conversations = ConversationService(
        repository,
        tickets,
        IntakeExtractionService(),
        ConfigurableIntakeProvider(settings, ai_models),
        audit_log,
    )
    return TicketServices(tickets=tickets, conversations=conversations)


class ConfigurableIntakeProvider:
    """Routes assistant replies to the configured provider with safe fallbacks.

    Flagged messages are answered with the fixed refusal locally so flagged
    text is never sent to an external API, and any Gemini failure degrades to
    the deterministic mock reply rather than losing the customer's message.
    """

    def __init__(self, settings: Settings, ai_models: AiModelService | None) -> None:
        self._settings = settings
        self._ai_models = ai_models
        self._mock = MockLlmProvider()
        self._gemini = GeminiApiLlmProvider(settings, ai_models)
        self._logger = get_logger(__name__)

    def build_assistant_message(self, intake: IntakeDetails, safety_flags: tuple[str, ...]) -> str:
        if safety_flags:
            return self._mock.build_assistant_message(intake, safety_flags)
        if self._uses_gemini():
            try:
                return self._gemini.build_assistant_message(intake, safety_flags)
            except AppError as error:
                self._logger.warning(
                    "Gemini provider unavailable; falling back to mock reply.",
                    extra={"error_code": error.code},
                )
        return self._mock.build_assistant_message(intake, safety_flags)

    def _uses_gemini(self) -> bool:
        # The configured provider is authoritative: a Gemini API key alone
        # never switches the provider, and Gemini is only called when a key
        # is actually available.
        provider = self._ai_models.provider() if self._ai_models else self._settings.llm_provider
        api_key = self._ai_models.api_key() if self._ai_models else self._settings.gemini_api_key
        return provider == "gemini_api" and bool(api_key)
