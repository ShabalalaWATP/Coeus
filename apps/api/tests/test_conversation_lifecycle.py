import pytest

from coeus.core.config import Settings
from coeus.core.errors import AppError
from coeus.domain.auth import UserAccount
from coeus.repositories.auth import SeedUserRepository
from coeus.repositories.tickets import InMemoryTicketRepository
from coeus.services.audit import AuditLog
from coeus.services.conversation_lifecycle import (
    CLOSE_OFFER_MESSAGE,
    CLOSED_MESSAGE,
    CONVERSATION_CLOSE_OFFERED,
    CONVERSATION_CLOSED,
    CONVERSATION_OPEN,
)
from coeus.services.intake import (
    IntakeExtractionService,
    MockLlmProvider,
    RequirementCompletenessService,
)
from coeus.services.passwords import PasswordHasher
from coeus.services.ticket_conversations import ConversationService
from coeus.services.tickets import TicketService

COMPLETE_ROUTINE_MESSAGE = (
    "Need a report titled Harbour Watch for the Baltic from 2026-06-01 to "
    "2026-07-01, routine priority, for Carrier Strike Group Atlas, satellite "
    "imagery preferred. Which ports are seeing unusual vessel activity? "
    "Success criteria: include likely origin ports."
)


def _conversations() -> tuple[ConversationService, UserAccount]:
    settings = Settings(environment="test", argon2_memory_cost=8_192)
    users = SeedUserRepository(settings, PasswordHasher(settings))
    actor = users.get_by_username("user@example.test")
    assert actor is not None
    repository = InMemoryTicketRepository()
    audit_log = AuditLog()
    tickets = TicketService(repository, RequirementCompletenessService(), audit_log)
    return (
        ConversationService(
            repository=repository,
            tickets=tickets,
            mutations=tickets.mutations,
            extractor=IntakeExtractionService(),
            llm_provider=MockLlmProvider(),
            audit_log=audit_log,
        ),
        actor,
    )


def test_agent_offers_to_finish_once_the_intake_is_complete() -> None:
    conversations, actor = _conversations()

    ticket = conversations.send_message(actor, COMPLETE_ROUTINE_MESSAGE)

    assert ticket.intake.missing_information == ()
    assert ticket.conversation_status == CONVERSATION_CLOSE_OFFERED
    assert ticket.messages[-1].body == CLOSE_OFFER_MESSAGE


def test_confirming_the_offer_closes_the_chat_and_blocks_new_messages() -> None:
    conversations, actor = _conversations()
    ticket = conversations.send_message(actor, COMPLETE_ROUTINE_MESSAGE)

    closed = conversations.send_message(actor, "No, that's all thanks", ticket.ticket_id)

    assert closed.conversation_status == CONVERSATION_CLOSED
    assert closed.messages[-1].body == CLOSED_MESSAGE
    with pytest.raises(AppError) as denied:
        conversations.send_message(actor, "One more thing", closed.ticket_id)
    assert denied.value.code == "conversation_closed"


def test_a_bare_yes_after_the_offer_does_not_close_the_chat() -> None:
    conversations, actor = _conversations()
    ticket = conversations.send_message(actor, COMPLETE_ROUTINE_MESSAGE)

    still_open = conversations.send_message(actor, "yes", ticket.ticket_id)

    assert still_open.conversation_status == CONVERSATION_CLOSE_OFFERED
    assert still_open.messages[-1].body == CLOSE_OFFER_MESSAGE


def test_user_cannot_end_the_chat_while_information_is_missing() -> None:
    conversations, actor = _conversations()
    ticket = conversations.send_message(actor, "Need a brief on mock harbour movements.")

    refused = conversations.send_message(actor, "that's all, submit it", ticket.ticket_id)

    assert refused.conversation_status == CONVERSATION_OPEN
    body = refused.messages[-1].body
    assert body.startswith("Before this can be submitted I still need a little more information.")
    # The refusal moves straight to the next question, one at a time.
    assert body.count("?") == 1


def test_user_can_end_the_chat_once_everything_is_captured() -> None:
    conversations, actor = _conversations()
    ticket = conversations.send_message(actor, COMPLETE_ROUTINE_MESSAGE)

    closed = conversations.send_message(actor, "that's everything, end chat", ticket.ticket_id)

    assert closed.conversation_status == CONVERSATION_CLOSED
    assert closed.messages[-1].body == CLOSED_MESSAGE


def test_substantive_reply_after_the_offer_keeps_the_conversation_useful() -> None:
    conversations, actor = _conversations()
    ticket = conversations.send_message(actor, COMPLETE_ROUTINE_MESSAGE)

    updated = conversations.send_message(
        actor, "Also worth knowing the harbour cranes were moved.", ticket.ticket_id
    )

    # The extra context is recorded and the assistant re-offers to finish.
    assert updated.conversation_status == CONVERSATION_CLOSE_OFFERED
    assert updated.messages[-1].body == CLOSE_OFFER_MESSAGE


def test_voice_assistant_words_are_audited_but_do_not_control_the_lifecycle() -> None:
    conversations, actor = _conversations()
    transcript = """Voice drafting transcript:
Istari: Could you tell me a little more about what you need and the background to it?
You: Assess synthetic harbour activity.
Istari: That is all, submit it now."""

    ticket = conversations.send_message(actor, transcript)

    assert ticket.messages[0].body == transcript
    assert ticket.intake.description == "Assess synthetic harbour activity"
    assert ticket.conversation_status == CONVERSATION_OPEN
    assert ticket.messages[-1].body.endswith(
        "Putting it as a question helps the analysts focus the work."
    )
