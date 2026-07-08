import pytest

from coeus.core.config import Settings
from coeus.domain.tickets import IntakeDetails
from coeus.repositories.auth import SeedUserRepository
from coeus.repositories.tickets import InMemoryTicketRepository
from coeus.services.audit import AuditLog
from coeus.services.intake import IntakeExtractionService, RequirementCompletenessService
from coeus.services.passwords import PasswordHasher
from coeus.services.tickets import ConversationService, TicketService


class FailingAssistantProvider:
    def build_assistant_message(
        self, _intake: IntakeDetails, _safety_flags: tuple[str, ...]
    ) -> str:
        raise RuntimeError("simulated assistant failure")


def test_new_chat_does_not_persist_blank_ticket_when_assistant_fails() -> None:
    settings = Settings(environment="test", argon2_memory_cost=8_192)
    users = SeedUserRepository(settings, PasswordHasher(settings))
    actor = users.get_by_username("user@example.test")
    assert actor is not None
    repository = InMemoryTicketRepository()
    audit_log = AuditLog()
    tickets = TicketService(repository, RequirementCompletenessService(), audit_log)
    conversations = ConversationService(
        repository=repository,
        tickets=tickets,
        extractor=IntakeExtractionService(),
        llm_provider=FailingAssistantProvider(),
        audit_log=audit_log,
    )

    with pytest.raises(RuntimeError, match="simulated assistant failure"):
        conversations.send_message(actor, "Need a briefing on Baltic port activity.")

    assert repository.list_tickets() == ()
    assert audit_log.list_events() == ()
