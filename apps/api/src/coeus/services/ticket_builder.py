from coeus.core.config import Settings
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
from coeus.services.tickets import (
    ConversationService,
    TicketService,
    TicketServices,
)


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
    def __init__(self, settings: Settings, ai_models: AiModelService | None) -> None:
        self._settings = settings
        self._ai_models = ai_models
        self._mock = MockLlmProvider()
        self._gemini = GeminiApiLlmProvider(settings, ai_models)

    def build_assistant_message(self, intake: IntakeDetails, safety_flags: tuple[str, ...]) -> str:
        if self._uses_gemini():
            return self._gemini.build_assistant_message(intake, safety_flags)
        return self._mock.build_assistant_message(intake, safety_flags)

    def _uses_gemini(self) -> bool:
        return self._settings.llm_provider == "gemini_api" or bool(
            self._ai_models and self._ai_models.api_key()
        )
