"""Application-owned confirmation for model-normalised intake suggestions."""

import re
from dataclasses import dataclass

from coeus.domain.tickets import ChatMessage, MessageAuthor
from coeus.services.intake_interpretation import IntakeInterpretation

_PRIORITY_CONFIRMATION = re.compile(
    r"^I interpreted that as (?P<value>critical|high|medium|routine|low) priority\. "
    r"Is that correct\? Reply yes or no\.$"
)
_TIME_CONFIRMATION = re.compile(
    r"^I interpreted the period as (?P<start>\d{4}-\d{2}-\d{2}) through "
    r"(?P<end>\d{4}-\d{2}-\d{2})\. Is that correct\? Reply yes or no\.$"
)
_AFFIRMATIVE = frozenset({"yes", "yes correct", "yes please", "correct", "that is correct"})
_NEGATIVE = frozenset({"no", "nope", "incorrect", "that is wrong", "not correct"})


@dataclass(frozen=True)
class PendingIntakeConfirmation:
    interpretation: IntakeInterpretation


def confirmation_prompt(interpretation: IntakeInterpretation) -> str:
    if interpretation.target_field == "priority":
        return (
            f"I interpreted that as {interpretation.normalised_value} priority. "
            "Is that correct? Reply yes or no."
        )
    if interpretation.target_field == "time_period":
        return (
            f"I interpreted the period as {interpretation.time_period_start} through "
            f"{interpretation.time_period_end}. Is that correct? Reply yes or no."
        )
    raise ValueError("Only closed intake values can be confirmed.")


def pending_confirmation(
    messages: tuple[ChatMessage, ...],
) -> PendingIntakeConfirmation | None:
    if not messages or messages[-1].author is not MessageAuthor.ASSISTANT:
        return None
    text = messages[-1].body
    priority = _PRIORITY_CONFIRMATION.fullmatch(text)
    if priority is not None:
        return PendingIntakeConfirmation(
            IntakeInterpretation(
                "priority",
                "customer-confirmed model suggestion",
                normalised_value=priority.group("value"),
            )
        )
    period = _TIME_CONFIRMATION.fullmatch(text)
    if period is not None:
        return PendingIntakeConfirmation(
            IntakeInterpretation(
                "time_period",
                "customer-confirmed model suggestion",
                time_period_start=period.group("start"),
                time_period_end=period.group("end"),
            )
        )
    return None


def confirmation_decision(message: str) -> bool | None:
    normalised = " ".join(re.sub(r"[^a-z0-9 ]", " ", message.casefold()).split())
    if normalised in _AFFIRMATIVE:
        return True
    if normalised in _NEGATIVE:
        return False
    return None
