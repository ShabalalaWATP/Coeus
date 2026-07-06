from dataclasses import replace
from re import search

from coeus.domain.tickets import IntakeDetails

REQUIRED_INTAKE_FIELDS = (
    "title",
    "description",
    "operational_question",
    "area_or_region",
    "priority",
    "required_output_format",
    "customer_success_criteria",
)

PROMPT_INJECTION_MARKERS = (
    "act as admin",
    "bypass rbac",
    "developer mode",
    "disable safety",
    "exfiltrate",
    "fabricate existing product",
    "fabricate product",
    "hidden prompt",
    "ignore previous instructions",
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


class MockLlmProvider:
    def build_assistant_message(self, intake: IntakeDetails, safety_flags: tuple[str, ...]) -> str:
        if "prompt_injection_attempt" in safety_flags:
            return "I can only help capture the requirement. Please provide the missing details."
        if intake.missing_information:
            missing = ", ".join(_humanise(field) for field in intake.missing_information[:3])
            return f"I need {missing} before this can be submitted."
        return "The intake is complete enough to submit for controlled search."


class IntakeExtractionService:
    def extract(self, message: str, existing: IntakeDetails | None = None) -> IntakeDetails:
        text = _normalise_spaces(message)
        lowered = text.casefold()
        base = existing or IntakeDetails()
        extracted = replace(
            base,
            title=base.title or _extract_title(text),
            description=base.description or text,
            operational_question=base.operational_question or _extract_question(text),
            area_or_region=base.area_or_region or _extract_region(text),
            priority=base.priority or _extract_priority(lowered),
            required_output_format=base.required_output_format or _extract_output_format(lowered),
            customer_success_criteria=base.customer_success_criteria
            or _extract_success_criteria(lowered),
            known_context=base.known_context or _extract_known_context(text),
        )
        return RequirementCompletenessService().with_completeness(extracted)

    def safety_flags_for(self, message: str) -> tuple[str, ...]:
        lowered = message.casefold()
        if any(marker in lowered for marker in PROMPT_INJECTION_MARKERS):
            return ("prompt_injection_attempt",)
        return ()


class RequirementCompletenessService:
    def with_completeness(self, intake: IntakeDetails) -> IntakeDetails:
        missing = tuple(
            field for field in REQUIRED_INTAKE_FIELDS if _is_blank(getattr(intake, field))
        )
        present = len(REQUIRED_INTAKE_FIELDS) - len(missing)
        confidence = round(present / len(REQUIRED_INTAKE_FIELDS), 2)
        return replace(intake, missing_information=missing, confidence=confidence)

    def is_complete_enough(self, intake: IntakeDetails) -> bool:
        return not intake.missing_information


def merge_intake(intake: IntakeDetails, updates: dict[str, str]) -> IntakeDetails:
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
    )


def _extract_title(text: str) -> str:
    lowered = text.casefold()
    if " titled " in lowered:
        start = lowered.index(" titled ") + len(" titled ")
        raw = text[start:].split(" for ", 1)[0].strip(" .")
        return raw.title()
    words = [word.strip(".,") for word in text.split() if word.strip(".,")]
    return " ".join(words[:6]).title() if words else "Untitled Requirement"


def _extract_question(text: str) -> str | None:
    if "?" in text:
        return text.split("?", 1)[0].strip() + "?"
    if any(word in text.casefold() for word in ("assess", "assessment", "brief", "need")):
        return "What does the customer need to understand?"
    return None


REGION_MARKERS = (" in ", " around ", " for ")
REGION_STOP_WORDS = ("the ", "a ", "an ")
PRIORITY_TERMS = ("critical", "urgent", "high", "medium", "routine", "low")


def _extract_region(text: str) -> str | None:
    lowered = text.casefold()
    for marker in REGION_MARKERS:
        if marker not in lowered:
            continue
        start = lowered.index(marker) + len(marker)
        candidate = text[start:]
        # Stop the region at the next locational marker or clause break so
        # "activity in the Baltic region for a planning exercise" yields
        # "Baltic Region" rather than the trailing purpose clause.
        cut = len(candidate)
        for stop in (*REGION_MARKERS, ". ", ", "):
            position = candidate.casefold().find(stop)
            if position != -1:
                cut = min(cut, position)
        candidate = candidate[:cut].strip(" .")
        for prefix in REGION_STOP_WORDS:
            if candidate.casefold().startswith(prefix):
                candidate = candidate[len(prefix) :]
        if candidate:
            return candidate.title()
    return None


def _extract_priority(lowered: str) -> str | None:
    for priority in PRIORITY_TERMS:
        if search(rf"\b{priority}\b", lowered):
            return "high" if priority == "urgent" else priority
    return None


def _extract_output_format(lowered: str) -> str | None:
    if "briefing" in lowered or "brief" in lowered:
        return "Briefing note"
    if "assessment" in lowered:
        return "Assessment"
    return None


def _extract_success_criteria(lowered: str) -> str | None:
    # Prefer the customer's own words: lift the sentence that talks about
    # success so the checklist reflects what they actually asked for.
    for sentence in lowered.split("."):
        cleaned = sentence.strip()
        if "success" in cleaned or "criteria" in cleaned:
            return cleaned[:220].capitalize() + "."
    if "decision" in lowered or "command" in lowered or "action" in lowered:
        return "Support a timely operational decision."
    return None


def _extract_known_context(text: str) -> str | None:
    if len(text) < 24:
        return None
    return text[:220]


def _is_blank(value: object) -> bool:
    return value is None or (isinstance(value, str) and value.strip() == "")


def _normalise_spaces(value: str) -> str:
    return " ".join(value.split())


def _humanise(field: str) -> str:
    return field.replace("_", " ")
