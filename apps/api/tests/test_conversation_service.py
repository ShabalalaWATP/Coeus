import json
from uuid import uuid4

import pytest

from coeus.core.config import Settings
from coeus.core.errors import AppError
from coeus.domain.enums import TicketState
from coeus.domain.tickets import AgentExecutionKind, IntakeDetails, TicketRecord
from coeus.integrations.llm_gateway import LlmCall
from coeus.repositories.auth import SeedUserRepository
from coeus.services.ai_models import AiModelService
from coeus.services.audit import AuditLog
from coeus.services.intake import (
    AdmittedAssistantReply,
    IntakeExtractionService,
)
from coeus.services.intake_provider_calls import PreparedIntakeReply
from coeus.services.passwords import PasswordHasher
from coeus.services.provider_admission import ProviderAdmissionController
from coeus.services.ticket_builder import ConfigurableIntakeProvider
from coeus.services.ticket_conversations import ConversationService
from workflow_authority_helpers import authorised_ticket_service


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
    audit_log = AuditLog()
    repository, tickets, authenticated = authorised_ticket_service(actor, audit_log)
    conversations = ConversationService(
        repository=repository,
        tickets=tickets,
        mutations=tickets.mutations,
        extractor=IntakeExtractionService(),
        llm_provider=FailingAssistantProvider(),
        audit_log=audit_log,
    )

    with pytest.raises(RuntimeError, match="simulated assistant failure"):
        conversations.send_message(authenticated, "Need a briefing on Baltic port activity.")

    assert repository.list_tickets() == ()
    assert audit_log.list_events() == ()


def test_failed_remote_fallback_refunds_provider_capacity() -> None:
    calls = 0

    def provider_reply(call: LlmCall) -> str:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise AppError(503, "provider_unavailable", "Synthetic provider failure.")
        data = json.loads(call.prompt)
        requested_field = data["missing_fields"][0]
        return json.dumps(
            {
                "action": "ask_missing_field",
                "strategy": "ask_one_field",
                "reason_codes": ["missing_required_field"],
                "suggested_field": requested_field,
                "abstain": False,
            }
        )

    settings = Settings(
        environment="test",
        argon2_memory_cost=8_192,
        llm_provider="gemini_api",
        gemini_api_key="synthetic-key",
    )
    users = SeedUserRepository(settings, PasswordHasher(settings))
    actor = users.get_by_username("user@example.test")
    assert actor is not None
    audit_log = AuditLog()
    repository, tickets, authenticated = authorised_ticket_service(actor, audit_log)
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

    first = conversations.send_message(authenticated, "Need a synthetic briefing.")
    second = conversations.send_message(authenticated, "Focus it on Baltic ports.", first.ticket_id)
    with pytest.raises(AppError) as denied:
        conversations.send_message(authenticated, "Need another synthetic briefing.")

    assert calls == 2
    assert second.messages[-1].body == (
        "Got it. So this reaches the right team, which area or region does it concern?"
    )
    assert denied.value.status_code == 429
    assert len(repository.list_tickets()) == 1
    run = second.agent_runs[-1]
    assert run.execution_kind == AgentExecutionKind.PROVIDER_BACKED
    assert run.provider == "gemini_api"
    assert run.model
    assert run.fallback_outcome == "not_used"
    assert run.validation_outcome == "passed"
    assert run.prompt_version == "intake-planner-v2"
    assert run.policy_version == "intake-planner-policy-v1"
    assert run.context_schema_version == "intake-extracted-fields-v1"
    assert run.input_hash and run.input_hash.startswith("sha256:")
    assert run.output_hash and run.output_hash.startswith("sha256:")
    assert "synthetic-key" not in repr(run)
    assert "Focus it on Baltic ports" not in repr(run)
    assert "Which area or region" not in repr(run)
    assert run.advice is not None
    assert run.advice.agent.value == "intake_planner"


def test_chat_byte_limits_reject_before_and_after_provider_reply(monkeypatch) -> None:
    settings = Settings(environment="test", argon2_memory_cost=8_192)
    actor = SeedUserRepository(settings, PasswordHasher(settings)).get_by_username(
        "user@example.test"
    )
    assert actor is not None
    audit = AuditLog()
    repository, tickets, authenticated = authorised_ticket_service(actor, audit)

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

    with pytest.raises(AppError, match="invalid response"):
        service.send_message(authenticated, "short")
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


def test_prepared_remote_provider_commits_and_complete_stop_closes() -> None:
    settings = Settings(environment="test", argon2_memory_cost=8_192)
    actor = SeedUserRepository(settings, PasswordHasher(settings)).get_by_username(
        "user@example.test"
    )
    assert actor is not None
    audit = AuditLog()
    repository, tickets, _authenticated = authorised_ticket_service(actor, audit)

    class PreparedRemote:
        def build_assistant_message(
            self, _intake: IntakeDetails, _safety_flags: tuple[str, ...]
        ) -> str:
            return "Legacy remote reply."

        def prepare_assistant_reply(
            self, _intake: IntakeDetails, _safety_flags: tuple[str, ...]
        ) -> PreparedIntakeReply:
            success = AdmittedAssistantReply("Legacy remote reply.", True)
            unavailable = AdmittedAssistantReply("Legacy local fallback.", False)
            return PreparedIntakeReply(True, unavailable, lambda: success)

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
        PreparedRemote(),
        audit,
        admission,
    )

    reply = service._assistant_reply(actor, IntakeDetails(), ())
    close_reply, status = service._reply_and_status(
        actor, "open", "finish here", IntakeDetails(missing_information=())
    )

    assert reply.text == "Legacy remote reply."
    assert admission.metrics_snapshot() == {"provider.admitted": 1}
    assert "completes the intake" in close_reply.text.casefold()
    assert status == "closed"


def test_mock_to_remote_switch_cannot_bypass_provider_admission() -> None:
    settings = Settings(environment="test", argon2_memory_cost=8_192)
    actor = SeedUserRepository(settings, PasswordHasher(settings)).get_by_username(
        "user@example.test"
    )
    assert actor is not None
    audit = AuditLog()
    repository, tickets, _authenticated = authorised_ticket_service(actor, audit)
    ai_models = AiModelService(settings, audit)
    ai_models.configure_api_key("admin-id", "admin@example.test", "synthetic-key")
    network_calls = 0

    def generate(_call: LlmCall) -> str:
        nonlocal network_calls
        network_calls += 1
        return json.dumps(
            {
                "requested_field": "priority",
                "reply": "ask_requested_field",
                "abstain": False,
            }
        )

    class SwitchingProvider(ConfigurableIntakeProvider):
        switched = False

        def prepare_assistant_reply(
            self, intake: IntakeDetails, safety_flags: tuple[str, ...]
        ) -> PreparedIntakeReply:
            prepared = super().prepare_assistant_reply(intake, safety_flags)
            if not self.switched:
                ai_models.select_provider("admin-id", "admin@example.test", "gemini_api")
                self.switched = True
            return prepared

    admission = ProviderAdmissionController(
        max_concurrent=1,
        max_calls_per_window=1,
        max_calls_per_principal=1,
        window_seconds=60,
    )
    provider = SwitchingProvider(settings, ai_models, text_generator=generate)
    service = ConversationService(
        repository,
        tickets,
        tickets.mutations,
        IntakeExtractionService(),
        provider,
        audit,
        admission,
    )
    intake = IntakeDetails(missing_information=("priority",))

    local = service._assistant_reply(actor, intake, ())
    without_admission = ConversationService(
        repository, tickets, tickets.mutations, IntakeExtractionService(), provider, audit
    )._assistant_reply(actor, intake, ())
    remote = service._assistant_reply(actor, intake, ())

    assert local.outcome == "local_provider"
    assert not local.provider_succeeded
    assert without_admission.outcome == "provider_admission_unavailable_fallback"
    assert network_calls == 1
    assert remote.provider_succeeded
    assert admission.metrics_snapshot() == {"provider.admitted": 1}


def test_invalid_remote_output_commits_capacity_and_records_safe_provenance() -> None:
    settings = Settings(
        environment="test",
        argon2_memory_cost=8_192,
        llm_provider="gemini_api",
        gemini_api_key="secret-that-must-not-be-stored",
        provider_circuit_failure_threshold=2,
    )
    actor = SeedUserRepository(settings, PasswordHasher(settings)).get_by_username(
        "user@example.test"
    )
    assert actor is not None
    audit = AuditLog()
    repository, tickets, authenticated = authorised_ticket_service(actor, audit)
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
        ConfigurableIntakeProvider(settings, None, text_generator=lambda _call: "malformed"),
        audit,
        admission,
    )

    ticket = service.send_message(authenticated, "Sensitive synthetic requirement text.")
    with pytest.raises(AppError) as denied:
        service.send_message(authenticated, "A second request should be rate limited.")

    run = ticket.agent_runs[-1]
    assert denied.value.status_code == 429
    assert run.execution_kind == AgentExecutionKind.PROVIDER_BACKED
    assert run.fallback_outcome == "deterministic"
    assert run.validation_outcome == "failed"
    assert run.error_class == "ProviderOutputValidationError"
    assert run.input_hash and run.output_hash
    assert "Sensitive synthetic requirement" not in repr(run)
    assert "malformed" not in repr(run)
    assert "secret-that-must-not-be-stored" not in repr(run)
