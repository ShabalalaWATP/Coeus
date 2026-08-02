from uuid import uuid4

import pytest

from coeus.domain.tickets import IntakeDetails, MessageAuthor
from coeus.services.conversation_reply_records import deterministic_reply
from coeus.services.intake_confirmation import (
    confirmation_decision,
    confirmation_prompt,
    pending_confirmation,
)
from coeus.services.intake_interpretation import IntakeInterpretation
from coeus.services.intake_interpretation_provider import AdmittedIntakeInterpretation
from coeus.services.intake_interpretation_records import finalise_interpreted_reply
from coeus.services.intake_retry import non_repeating_intake_reply
from coeus.services.ticket_records import message


def test_priority_and_period_confirmations_round_trip_from_assistant_copy() -> None:
    ticket_id = uuid4()
    priority = IntakeInterpretation("priority", "routine-ish", normalised_value="routine")
    period = IntakeInterpretation(
        "time_period",
        "the previous reporting year",
        time_period_start="2025-01-01",
        time_period_end="2025-12-31",
    )

    for interpretation in (priority, period):
        copy = confirmation_prompt(interpretation)
        pending = pending_confirmation((message(ticket_id, MessageAuthor.ASSISTANT, copy),))

        assert pending is not None
        assert pending.interpretation.target_field == interpretation.target_field
        assert pending.interpretation.normalised_value == interpretation.normalised_value
        assert pending.interpretation.time_period_start == interpretation.time_period_start
        assert pending.interpretation.time_period_end == interpretation.time_period_end


def test_only_exact_latest_assistant_confirmation_is_trusted() -> None:
    ticket_id = uuid4()
    copy = confirmation_prompt(IntakeInterpretation("priority", "low-ish", normalised_value="low"))

    assert pending_confirmation(()) is None
    assert pending_confirmation((message(ticket_id, MessageAuthor.USER, copy),)) is None
    assert (
        pending_confirmation((message(ticket_id, MessageAuthor.ASSISTANT, f"modified {copy}"),))
        is None
    )


@pytest.mark.parametrize(
    ("answer", "expected"),
    (("yes", True), ("That is correct.", True), ("nope", False), ("maybe", None)),
)
def test_confirmation_decision_is_closed_and_deterministic(
    answer: str, expected: bool | None
) -> None:
    assert confirmation_decision(answer) is expected


def test_free_text_cannot_be_turned_into_a_confirmation() -> None:
    with pytest.raises(ValueError, match="closed intake values"):
        confirmation_prompt(IntakeInterpretation("area_or_region", "Baltic"))


def test_retry_copy_is_unchanged_when_no_intake_field_is_active() -> None:
    assert non_repeating_intake_reply((), IntakeDetails(), "Complete.") == "Complete."


def test_interpretation_provenance_cannot_hide_lifecycle_copy() -> None:
    reply = deterministic_reply(
        "Before this can be submitted, priority is still needed.",
        "close_refused_missing_information",
    )
    outcome = AdmittedIntakeInterpretation(
        IntakeInterpretation("priority", "banana", normalised_value="critical"),
        True,
        outcome="provider_interpretation_confirmation_requested",
    )

    recorded = finalise_interpreted_reply(
        reply,
        (),
        IntakeDetails(missing_information=("priority",)),
        outcome,
    )

    assert recorded.text == reply.text
