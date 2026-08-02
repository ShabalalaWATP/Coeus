"""Transcript-derived guidance which prevents repeated intake questions."""

from coeus.domain.tickets import ChatMessage, IntakeDetails, MessageAuthor
from coeus.services.intake_interpretation import active_intake_field
from coeus.services.intake_standard import INTAKE_STANDARD, IntakeFieldStandard


def non_repeating_intake_reply(
    messages: tuple[ChatMessage, ...], intake: IntakeDetails, proposed_text: str
) -> str:
    field = active_intake_field(intake)
    entry = next((item for item in INTAKE_STANDARD if item.field == field), None)
    if entry is None:
        return proposed_text
    guidance = _guidance(entry)
    prior_attempts = sum(
        1
        for message in messages
        if message.author is MessageAuthor.ASSISTANT
        and (_same_question(message.body, proposed_text, entry) or message.body in guidance)
    )
    if prior_attempts == 0:
        return proposed_text
    if prior_attempts == 1:
        return guidance[0]
    return guidance[1 + (prior_attempts % 2)]


def _same_question(previous: str, proposed: str, entry: IntakeFieldStandard) -> bool:
    return previous == proposed or (
        previous.endswith(entry.question) and proposed.endswith(entry.question)
    )


def _guidance(entry: IntakeFieldStandard) -> tuple[str, str, str]:
    example = entry.example.rstrip("?.") + "."
    return (
        f"I couldn't confidently interpret that as {entry.label.lower()}. "
        f"Please reply in a form such as: {example}",
        f"That detail is still unresolved. Open Edit details and set "
        f"{entry.label.lower()} directly; I will continue once it is saved.",
        f"{entry.label} still needs a valid value in Edit details before this "
        f"request can continue.",
    )
