import json
from collections.abc import Callable
from uuid import UUID, uuid4

from coeus.core.config import Settings
from coeus.domain.auth import AuthenticatedSession
from coeus.domain.enums import TicketState
from coeus.domain.tickets import IntakeDetails, MessageAuthor, TicketRecord
from coeus.integrations.llm_gateway import LlmCall
from coeus.repositories.auth import SeedUserRepository
from coeus.services.audit import AuditLog
from coeus.services.configurable_intake_provider import ConfigurableIntakeProvider
from coeus.services.intake import IntakeExtractionService, MockLlmProvider
from coeus.services.intake_confirmation import confirmation_prompt
from coeus.services.intake_interpretation import IntakeInterpretation
from coeus.services.intake_standard import INTAKE_STANDARD
from coeus.services.intake_turn_interpretation import interpret_intake_turn
from coeus.services.passwords import PasswordHasher
from coeus.services.provider_admission import ProviderAdmissionController
from coeus.services.ticket_conversations import ConversationService
from coeus.services.ticket_records import message as message_record
from workflow_authority_helpers import authorised_ticket_service


def _priority_ticket(actor_id: UUID) -> TicketRecord:
    ticket_id = uuid4()
    question = next(item.question for item in INTAKE_STANDARD if item.field == "priority")
    return TicketRecord(
        ticket_id=ticket_id,
        reference="TCK-REGRESSION",
        requester_user_id=actor_id,
        state=TicketState.INFO_REQUIRED,
        intake=IntakeDetails(
            title="Synthetic watch",
            description="Assess synthetic activity.",
            operational_question="What changed?",
            area_or_region="Baltic ports",
            time_period_start="2026-01-01",
            time_period_end="2026-12-31",
            missing_information=("priority",),
        ),
        messages=(
            message_record(
                ticket_id,
                MessageAuthor.ASSISTANT,
                f"Thanks, that helps. {question}",
            ),
        ),
    )


def _service(
    generator: Callable[[LlmCall], str],
) -> tuple[ConversationService, AuthenticatedSession, TicketRecord]:
    settings = Settings(
        environment="test",
        argon2_memory_cost=8_192,
        llm_provider="gemini_api",
        gemini_api_key="synthetic-key",
    )
    actor = SeedUserRepository(settings, PasswordHasher(settings)).get_by_username(
        "user@example.test"
    )
    assert actor is not None
    audit = AuditLog()
    repository, tickets, authenticated = authorised_ticket_service(actor, audit)
    ticket = _priority_ticket(actor.user_id)
    repository.save(ticket)
    service = ConversationService(
        repository,
        tickets,
        tickets.mutations,
        IntakeExtractionService(),
        ConfigurableIntakeProvider(settings, None, text_generator=generator),
        audit,
        ProviderAdmissionController(
            max_concurrent=1,
            max_calls_per_window=2,
            max_calls_per_principal=2,
            window_seconds=60,
        ),
    )
    return service, authenticated, ticket


def _low_priority_output() -> str:
    return json.dumps(
        {
            "target_field": "priority",
            "evidence": "not especially urgent",
            "normalised_value": "low",
            "time_period_start": None,
            "time_period_end": None,
            "abstain": False,
        }
    )


def test_voice_interpretation_egresses_only_the_active_fields_answer() -> None:
    calls: list[LlmCall] = []

    def interpret(call: LlmCall) -> str:
        calls.append(call)
        return _low_priority_output()

    service, authenticated, ticket = _service(interpret)
    transcript = """Voice drafting transcript:
Istari: Which unit or team should this be logged against?
You: UNRELATED_SENTINEL_TEAM
Istari: How urgent is this: critical, high, medium, routine or low?
You: not especially urgent"""

    updated = service.send_message(authenticated, transcript, ticket.ticket_id)

    assert len(calls) == 1
    assert "not especially urgent" in calls[0].prompt
    assert "UNRELATED_SENTINEL_TEAM" not in calls[0].prompt
    assert updated.intake.requesting_unit == "UNRELATED_SENTINEL_TEAM"
    assert updated.intake.priority is None


def test_unrecognised_voice_question_cannot_extend_the_active_field_answer() -> None:
    calls: list[LlmCall] = []

    def interpret(call: LlmCall) -> str:
        calls.append(call)
        return _low_priority_output()

    service, authenticated, ticket = _service(interpret)
    transcript = """Voice drafting transcript:
Istari: How urgent is this: critical, high, medium, routine or low?
You: not especially urgent
Istari: Tell me the unrelated handling note.
You: UNRELATED_SECRET_SENTINEL"""

    updated = service.send_message(authenticated, transcript, ticket.ticket_id)

    assert len(calls) == 1
    assert "not especially urgent" in calls[0].prompt
    assert "UNRELATED_SECRET_SENTINEL" not in calls[0].prompt
    assert updated.intake.priority is None


def test_unrecognised_voice_question_cannot_fill_an_active_free_text_field() -> None:
    existing = IntakeDetails(
        description="Assess synthetic activity.",
        operational_question="What changed?",
        area_or_region="Baltic ports",
        time_period_start="2026-01-01",
        time_period_end="2026-12-31",
        priority="routine",
        missing_information=("requesting_unit",),
    )
    transcript = """Voice drafting transcript:
Istari: Tell me the unrelated handling note.
You: UNRELATED_SECRET_SENTINEL"""

    updated = IntakeExtractionService().extract(transcript, existing)

    assert updated.requesting_unit is None


def test_close_intent_does_not_fill_a_missing_field_or_hide_close_refusal() -> None:
    service, authenticated, ticket = _service(lambda _call: "{}")

    updated = service.send_message(authenticated, "please submit", ticket.ticket_id)

    assert updated.intake.priority is None
    assert updated.messages[-1].body.startswith(
        "Before this can be submitted I still need a little more information."
    )
    assert "How urgent is this" in updated.messages[-1].body
    assert "couldn't confidently interpret" not in updated.messages[-1].body


def test_voice_clarification_uses_only_the_answer_mapped_to_that_field() -> None:
    existing = IntakeDetails(
        description="Assess synthetic activity.",
        operational_question="What changed?",
        area_or_region="Europe",
        time_period_start="2026-01-01",
        time_period_end="2026-12-31",
        priority="routine",
    )
    transcript = """Voice drafting transcript:
Istari: Which area or region does it concern?
You: Baltic ports
Istari: Which unit or team should this be logged against?
You: UNRELATED_SENTINEL_TEAM"""

    result = interpret_intake_turn(
        uuid4(),
        transcript,
        existing,
        (),
        IntakeExtractionService(),
        MockLlmProvider(),
        None,
    )

    assert result.intake.area_or_region == "Baltic ports"
    assert result.intake.requesting_unit == "UNRELATED_SENTINEL_TEAM"


def test_voice_end_intent_cannot_fill_a_required_field_or_hide_close_refusal() -> None:
    calls = 0

    def should_not_run(_call: LlmCall) -> str:
        nonlocal calls
        calls += 1
        return _low_priority_output()

    service, authenticated, ticket = _service(should_not_run)
    transcript = """Voice drafting transcript:
Istari: How urgent is this: critical, high, medium, routine or low?
You: finish here"""

    updated = service.send_message(authenticated, transcript, ticket.ticket_id)

    assert calls == 0
    assert updated.intake.priority is None
    assert updated.messages[-1].body.startswith(
        "Before this can be submitted I still need a little more information."
    )
    assert "How urgent is this" in updated.messages[-1].body


def test_voice_end_intent_is_not_a_free_text_intake_answer() -> None:
    existing = IntakeDetails(
        description="Assess synthetic activity.",
        operational_question="What changed?",
        area_or_region="Baltic ports",
        time_period_start="2026-01-01",
        time_period_end="2026-12-31",
        priority="routine",
        missing_information=("requesting_unit",),
    )
    transcript = """Voice drafting transcript:
Istari: Which unit or team should this be logged against?
You: finish here"""

    updated = IntakeExtractionService().extract(transcript, existing)

    assert updated.requesting_unit is None
    assert "requesting_unit" in updated.missing_information


def test_voice_keeps_a_valid_answer_before_a_separate_end_turn() -> None:
    existing = IntakeDetails(
        description="Assess synthetic activity.",
        operational_question="What changed?",
        area_or_region="Baltic ports",
        time_period_start="2026-01-01",
        time_period_end="2026-12-31",
        priority="routine",
        missing_information=("requesting_unit",),
    )
    transcript = """Voice drafting transcript:
Istari: Which unit or team should this be logged against?
You: Maritime Analysis Team
You: finish here"""

    updated = IntakeExtractionService().extract(transcript, existing)

    assert updated.requesting_unit == "Maritime Analysis Team"


def test_stale_confirmation_cannot_overwrite_a_newer_manual_value() -> None:
    suggestion = IntakeInterpretation(
        "priority",
        "not especially urgent",
        normalised_value="low",
    )
    existing = IntakeDetails(
        description="Assess synthetic activity.",
        operational_question="What changed?",
        area_or_region="Baltic ports",
        time_period_start="2026-01-01",
        time_period_end="2026-12-31",
        priority="routine",
        missing_information=("requesting_unit",),
    )
    ticket_id = uuid4()
    messages = (
        message_record(
            ticket_id,
            MessageAuthor.ASSISTANT,
            confirmation_prompt(suggestion),
        ),
    )

    result = interpret_intake_turn(
        uuid4(),
        "yes",
        existing,
        messages,
        IntakeExtractionService(),
        MockLlmProvider(),
        None,
    )

    assert result.intake.priority == "routine"
    assert result.intake.requesting_unit is None
    assert not result.allow_provider_reply

    substantive = interpret_intake_turn(
        uuid4(),
        "Maritime Analysis Team",
        existing,
        messages,
        IntakeExtractionService(),
        MockLlmProvider(),
        None,
    )

    assert substantive.intake.priority == "routine"
    assert substantive.intake.requesting_unit == "Maritime Analysis Team"
