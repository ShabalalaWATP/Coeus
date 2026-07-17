"""Apply a direct customer answer to the intake detail currently being elicited."""

import re
from dataclasses import replace

from coeus.domain.tickets import IntakeDetails
from coeus.services import intake_extractors as extractors

_NON_ANSWERS = frozenset(
    {"", "i don't know", "i do not know", "not sure", "unsure", "n/a", "none", "no"}
)
_TIME_WORDS = re.compile(
    r"\b(?:day|days|week|weeks|month|months|year|years|january|february|march|april|may|"
    r"june|july|august|september|october|november|december|today|tomorrow|yesterday)\b",
    re.IGNORECASE,
)


def apply_direct_answer(
    intake: IntakeDetails,
    field: str,
    answer: str,
    *,
    overwrite: bool = False,
) -> IntakeDetails:
    """Apply a bounded answer to one known field, without inferring another field."""
    cleaned = extractors.normalise_spaces(answer).strip(" .")
    if _is_non_answer(cleaned):
        return intake
    if field == "time_period":
        return _apply_time_period(intake, cleaned, overwrite)
    current = getattr(intake, field, None)
    if current and not overwrite:
        return intake
    value = _normalise_field_value(field, cleaned)
    if value is None:
        return intake
    updated = _replace_answer_field(intake, field, value)
    if field == "description" and updated.known_context is None and len(value) >= 24:
        updated = replace(updated, known_context=value[:220])
    return updated


def _apply_time_period(intake: IntakeDetails, answer: str, overwrite: bool) -> IntakeDetails:
    if intake.time_period_start and not overwrite:
        return intake
    start, end = extractors.extract_time_window(answer)
    if start is None:
        if extractors.contains_explicit_date_range(answer) or not _TIME_WORDS.search(answer):
            return intake
        start = end = answer[:120]
    return replace(intake, time_period_start=start, time_period_end=end)


def _normalise_field_value(field: str, value: str) -> str | None:
    if field == "priority":
        return extractors.extract_priority(value.casefold())
    if field == "intelligence_disciplines":
        return extractors.extract_disciplines(value.casefold()) or value[:160]
    if field == "required_output_format":
        return extractors.extract_output_format(value.casefold()) or value[:120]
    if field == "supported_operation":
        return extractors.extract_operation(value) or value[:160]
    return value[:120] if field == "title" else value[:220]


def _is_non_answer(value: str) -> bool:
    lowered = value.casefold().strip()
    return lowered in _NON_ANSWERS or lowered.startswith(("i don't know ", "not sure "))


def _replace_answer_field(intake: IntakeDetails, field: str, value: str) -> IntakeDetails:
    replacements = {
        "title": lambda: replace(intake, title=value),
        "description": lambda: replace(intake, description=value),
        "operational_question": lambda: replace(intake, operational_question=value),
        "area_or_region": lambda: replace(intake, area_or_region=value),
        "priority": lambda: replace(intake, priority=value),
        "deadline": lambda: replace(intake, deadline=value),
        "required_output_format": lambda: replace(intake, required_output_format=value),
        "customer_success_criteria": lambda: replace(intake, customer_success_criteria=value),
        "requesting_unit": lambda: replace(intake, requesting_unit=value),
        "intelligence_disciplines": lambda: replace(intake, intelligence_disciplines=value),
        "supported_operation": lambda: replace(intake, supported_operation=value),
        "urgency_justification": lambda: replace(intake, urgency_justification=value),
    }
    replacement = replacements.get(field)
    return replacement() if replacement is not None else intake
