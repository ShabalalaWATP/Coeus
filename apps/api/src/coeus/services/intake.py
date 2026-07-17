import re
from dataclasses import dataclass, replace
from typing import Protocol

from coeus.domain.tickets import IntakeDetails
from coeus.services import intake_extractors as extractors
from coeus.services.intake_answers import apply_direct_answer
from coeus.services.intake_standard import (
    REQUIRED_INTAKE_FIELDS as REQUIRED_INTAKE_FIELDS,
)
from coeus.services.intake_standard import (
    applicable_entries,
    entry_satisfied,
    next_elicitation,
)
from coeus.services.intake_transcripts import voice_answers, voice_turns

# Substring markers are matched against a normalised message (casefolded,
# zero-width characters stripped, whitespace collapsed), so case, doubled
# spaces and newlines between words cannot bypass them.
PROMPT_INJECTION_MARKERS = (
    "act as admin",
    "bypass rbac",
    "developer mode",
    "disable safety",
    "exfiltrate",
    "fabricate existing product",
    "fabricate product",
    "hidden prompt",
    "ignore safety",
    "jailbreak",
    "make me admin",
    "override access controls",
    "reveal hidden prompt",
    "show internal instructions",
    "system prompt",
    "tool call",
    "use admin tool",
)

# Regex families catch phrasing variants such as "ignore all previous
# instructions" or "disregard prior instructions".
PROMPT_INJECTION_PATTERNS = (
    re.compile(
        r"\b(?:ignore|disregard|forget)\s+(?:all\s+|any\s+)?"
        r"(?:previous|prior|above|earlier)\s+instructions\b"
    ),
)

_ZERO_WIDTH_PATTERN = re.compile("[\u200b\u200c\u200d\u2060\ufeff]")

# Rotated deterministically so replies do not all open the same way. The chat
# must feel like a conversation, never like a form being filled in.
ACKNOWLEDGEMENTS = (
    "Got it.",
    "Thanks, that helps.",
    "Understood.",
    "Noted, thank you.",
)


class IntakeAssistantProvider(Protocol):
    def build_assistant_message(self, intake: IntakeDetails, safety_flags: tuple[str, ...]) -> str:
        """Build the requester-facing assistant response for extracted intake."""


@dataclass(frozen=True)
class AdmittedAssistantReply:
    """Assistant text plus whether operator-funded provider work succeeded."""

    text: str
    provider_succeeded: bool


class MockLlmProvider:
    def build_assistant_message(self, intake: IntakeDetails, safety_flags: tuple[str, ...]) -> str:
        if "prompt_injection_attempt" in safety_flags:
            return "I can only help capture the requirement. Please provide the missing details."
        entry = next_elicitation(intake.missing_information)
        if entry is not None:
            applicable = applicable_entries(intake.priority)
            captured = sum(1 for item in applicable if entry_satisfied(item, intake))
            opener = ACKNOWLEDGEMENTS[captured % len(ACKNOWLEDGEMENTS)]
            return f"{opener} {entry.question}"
        return (
            "I think I have everything I need. Is there anything else you "
            "would like to add, or shall we finish here?"
        )


class IntakeExtractionService:
    def extract(self, message: str, existing: IntakeDetails | None = None) -> IntakeDetails:
        turns = voice_turns(message)
        if turns is None:
            return self._extract_text(message, existing or IntakeDetails())
        original = existing or IntakeDetails()
        requester_text = " ".join(turn.text for turn in turns if turn.speaker == "user")
        current = (
            self._extract_text(
                requester_text,
                original,
                apply_context=False,
                infer_title=False,
            )
            if requester_text
            else RequirementCompletenessService().with_completeness(original)
        )
        for answer in voice_answers(turns):
            if answer.field is None:
                current = self._extract_text(answer.text, current)
            else:
                current = apply_direct_answer(
                    current,
                    answer.field,
                    answer.text,
                    overwrite=not _field_has_value(original, answer.field),
                )
                current = RequirementCompletenessService().with_completeness(current)
        return current

    def _extract_text(
        self,
        message: str,
        existing: IntakeDetails,
        *,
        apply_context: bool = True,
        infer_title: bool | None = None,
    ) -> IntakeDetails:
        text = extractors.normalise_spaces(message)
        lowered = text.casefold()
        base = RequirementCompletenessService().with_completeness(existing)
        expected = next_elicitation(base.missing_information)
        time_period_start, time_period_end = extractors.extract_time_window(text)
        can_infer_title = (
            infer_title
            if infer_title is not None
            else (base.description is None or (expected is not None and expected.field == "title"))
        )
        extracted = replace(
            base,
            title=base.title or (extractors.extract_title(text) if can_infer_title else None),
            description=base.description or text,
            operational_question=base.operational_question or extractors.extract_question(text),
            area_or_region=base.area_or_region or extractors.extract_region(text),
            time_period_start=base.time_period_start or time_period_start,
            time_period_end=base.time_period_end or time_period_end,
            priority=base.priority or extractors.extract_priority(lowered),
            deadline=base.deadline or extractors.extract_deadline(text),
            required_output_format=base.required_output_format
            or extractors.extract_output_format(lowered),
            customer_success_criteria=base.customer_success_criteria
            or extractors.extract_success_criteria(text),
            known_context=base.known_context or extractors.extract_known_context(text),
            requesting_unit=base.requesting_unit or extractors.extract_requesting_unit(text),
            intelligence_disciplines=base.intelligence_disciplines
            or extractors.extract_disciplines(lowered),
            supported_operation=base.supported_operation or extractors.extract_operation(text),
            urgency_justification=base.urgency_justification
            or extractors.extract_urgency_justification(text),
        )
        if apply_context and expected is not None:
            extracted = apply_direct_answer(extracted, expected.field, text)
        return RequirementCompletenessService().with_completeness(extracted)

    def safety_flags_for(self, message: str) -> tuple[str, ...]:
        normalised = _normalise_for_scanning(message)
        if any(pattern.search(normalised) for pattern in PROMPT_INJECTION_PATTERNS):
            return ("prompt_injection_attempt",)
        if any(marker in normalised for marker in PROMPT_INJECTION_MARKERS):
            return ("prompt_injection_attempt",)
        return ()


class RequirementCompletenessService:
    def with_completeness(self, intake: IntakeDetails) -> IntakeDetails:
        applicable = applicable_entries(intake.priority)
        missing = tuple(entry.field for entry in applicable if not entry_satisfied(entry, intake))
        present = len(applicable) - len(missing)
        confidence = round(present / len(applicable), 2)
        return replace(intake, missing_information=missing, confidence=confidence)

    def is_complete_enough(self, intake: IntakeDetails) -> bool:
        return not self.with_completeness(intake).missing_information


def merge_intake(intake: IntakeDetails, updates: dict[str, str | None]) -> IntakeDetails:
    return replace(
        intake,
        title=updates.get("title", intake.title),
        description=updates.get("description", intake.description),
        operational_question=updates.get("operational_question", intake.operational_question),
        area_or_region=updates.get("area_or_region", intake.area_or_region),
        time_period_start=updates.get("time_period_start", intake.time_period_start),
        time_period_end=updates.get("time_period_end", intake.time_period_end),
        priority=updates.get("priority", intake.priority),
        deadline=updates.get("deadline", intake.deadline),
        required_output_format=updates.get("required_output_format", intake.required_output_format),
        known_context=updates.get("known_context", intake.known_context),
        restrictions_or_caveats=updates.get(
            "restrictions_or_caveats", intake.restrictions_or_caveats
        ),
        customer_success_criteria=updates.get(
            "customer_success_criteria", intake.customer_success_criteria
        ),
        suggested_acg_context=updates.get("suggested_acg_context", intake.suggested_acg_context),
        requesting_unit=updates.get("requesting_unit", intake.requesting_unit),
        intelligence_disciplines=updates.get(
            "intelligence_disciplines", intake.intelligence_disciplines
        ),
        supported_operation=updates.get("supported_operation", intake.supported_operation),
        urgency_justification=updates.get("urgency_justification", intake.urgency_justification),
    )


def _normalise_for_scanning(value: str) -> str:
    stripped = _ZERO_WIDTH_PATTERN.sub("", value)
    return " ".join(stripped.casefold().split())


def _field_has_value(intake: IntakeDetails, field: str) -> bool:
    value = intake.time_period_start if field == "time_period" else getattr(intake, field, None)
    return isinstance(value, str) and bool(value.strip())
