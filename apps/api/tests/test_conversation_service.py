from uuid import uuid4

import pytest

from coeus.core.config import Settings
from coeus.core.errors import AppError
from coeus.domain.enums import TicketState
from coeus.domain.tickets import IntakeDetails, TicketRecord
from coeus.repositories.auth import SeedUserRepository
from coeus.repositories.tickets import InMemoryTicketRepository
from coeus.services.audit import AuditLog
from coeus.services.intake import IntakeExtractionService, RequirementCompletenessService
from coeus.services.passwords import PasswordHasher
from coeus.services.provider_admission import ProviderAdmissionController
from coeus.services.ticket_builder import ConfigurableIntakeProvider
from coeus.services.ticket_conversations import ConversationService
from coeus.services.tickets import TicketService


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
        mutations=tickets.mutations,
        extractor=IntakeExtractionService(),
        llm_provider=FailingAssistantProvider(),
        audit_log=audit_log,
    )

    with pytest.raises(RuntimeError, match="simulated assistant failure"):
        conversations.send_message(actor, "Need a briefing on Baltic port activity.")

    assert repository.list_tickets() == ()
    assert audit_log.list_events() == ()


def test_failed_remote_fallback_refunds_provider_capacity() -> None:
    calls = 0

    def provider_reply(_call: object) -> str:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise AppError(503, "provider_unavailable", "Synthetic provider failure.")
        return "Synthetic remote reply."

    settings = Settings(
        environment="test",
        argon2_memory_cost=8_192,
        llm_provider="gemini_api",
        gemini_api_key="synthetic-key",
    )
    users = SeedUserRepository(settings, PasswordHasher(settings))
    actor = users.get_by_username("user@example.test")
    assert actor is not None
    repository = InMemoryTicketRepository()
    audit_log = AuditLog()
    tickets = TicketService(repository, RequirementCompletenessService(), audit_log)
    admission = ProviderAdmissionController(
        max_concurrent=1,
        max_calls_per_window=1,
        max_calls_per_principal=1,
        window_seconds=60,
    )
    conversations = ConversationService(
        repository,
        tickets,
        tickets.mutations,
        IntakeExtractionService(),
        ConfigurableIntakeProvider(settings, None, text_generator=provider_reply),
        audit_log,
        admission,
    )

    first = conversations.send_message(actor, "Need a synthetic briefing.")
    second = conversations.send_message(actor, "Focus it on Baltic ports.", first.ticket_id)
    with pytest.raises(AppError) as denied:
        conversations.send_message(actor, "Need another synthetic briefing.")

    assert calls == 2
    assert second.messages[-1].body == "Synthetic remote reply."
    assert denied.value.status_code == 429
    assert len(repository.list_tickets()) == 1


def test_chat_byte_limits_reject_before_and_after_provider_reply(monkeypatch) -> None:
    settings = Settings(environment="test", argon2_memory_cost=8_192)
    actor = SeedUserRepository(settings, PasswordHasher(settings)).get_by_username(
        "user@example.test"
    )
    assert actor is not None
    repository = InMemoryTicketRepository()
    audit = AuditLog()
    tickets = TicketService(repository, RequirementCompletenessService(), audit)

    class OversizedReply:
        def build_assistant_message(
            self, _intake: IntakeDetails, _safety_flags: tuple[str, ...]
        ) -> str:
            return "x" * 20

    service = ConversationService(
        repository,
        tickets,
        tickets.mutations,
        IntakeExtractionService(),
        OversizedReply(),
        audit,
    )
    monkeypatch.setattr("coeus.services.ticket_conversations.MAX_ASSISTANT_REPLY_BYTES", 1)
    monkeypatch.setattr("coeus.services.ticket_conversations.MAX_CHAT_HISTORY_BYTES", 10)

    with pytest.raises(AppError, match="history limit"):
        service.send_message(actor, "short")
    with pytest.raises(AppError, match="history limit"):
        service._ensure_chat_budget(
            TicketRecord(
                ticket_id=uuid4(),
                reference="TCK-BYTE-LIMIT",
                requester_user_id=actor.user_id,
                state=TicketState.DRAFT_INTAKE,
                intake=IntakeDetails(),
            ),
            "y" * 20,
        )
    assert repository.list_tickets() == ()


def test_legacy_remote_provider_commits_and_complete_stop_closes() -> None:
    settings = Settings(environment="test", argon2_memory_cost=8_192)
    actor = SeedUserRepository(settings, PasswordHasher(settings)).get_by_username(
        "user@example.test"
    )
    assert actor is not None
    repository = InMemoryTicketRepository()
    audit = AuditLog()
    tickets = TicketService(repository, RequirementCompletenessService(), audit)

    class LegacyRemote:
        def uses_operator_provider(self) -> bool:
            return True

        def build_assistant_message(
            self, _intake: IntakeDetails, _safety_flags: tuple[str, ...]
        ) -> str:
            return "Legacy remote reply."

    admission = ProviderAdmissionController(
        max_concurrent=1,
        max_calls_per_window=1,
        max_calls_per_principal=1,
        window_seconds=60,
    )
    service = ConversationService(
        repository,
        tickets,
        tickets.mutations,
        IntakeExtractionService(),
        LegacyRemote(),
        audit,
        admission,
    )

    reply = service._assistant_reply(actor, IntakeDetails(), ())
    close_reply, status = service._reply_and_status(
        actor, "open", "finish here", IntakeDetails(missing_information=())
    )

    assert reply == "Legacy remote reply."
    assert admission.metrics_snapshot() == {"provider.admitted": 1}
    assert "completes the intake" in close_reply.casefold()
    assert status == "closed"
