import re
from dataclasses import replace
from typing import Protocol

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


class IntakeAssistantProvider(Protocol):
    def build_assistant_message(self, intake: IntakeDetails, safety_flags: tuple[str, ...]) -> str:
        """Build the requester-facing assistant response for extracted intake."""


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
        time_period_start, time_period_end = _extract_time_window(text)
        extracted = replace(
            base,
            title=base.title or _extract_title(text),
            description=base.description or text,
            operational_question=base.operational_question or _extract_question(text),
            area_or_region=base.area_or_region or _extract_region(text),
            time_period_start=base.time_period_start or time_period_start,
            time_period_end=base.time_period_end or time_period_end,
            priority=base.priority or _extract_priority(lowered),
            deadline=base.deadline or _extract_deadline(text),
            required_output_format=base.required_output_format or _extract_output_format(lowered),
            customer_success_criteria=base.customer_success_criteria
            or _extract_success_criteria(text),
            known_context=base.known_context or _extract_known_context(text),
        )
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


REQUIREMENT_CUES = frozenset(
    {
        "need",
        "needs",
        "request",
        "require",
        "required",
        "assess",
        "assessment",
        "brief",
        "briefing",
        "report",
        "analysis",
        "provide",
        "produce",
        "want",
    }
)


def _extract_title(text: str) -> str | None:
    lowered = text.casefold()
    if " titled " in lowered:
        start = lowered.index(" titled ") + len(" titled ")
        raw = text[start:].split(" for ", 1)[0].strip(" .")
        return raw.title()
    # Fall back to the first six words only when the message reads like a
    # requirement statement, so incidental chat does not become a title.
    if not frozenset(re.findall(r"[a-z0-9]+", lowered)).intersection(REQUIREMENT_CUES):
        return None
    words = [word.strip(".,") for word in text.split() if word.strip(".,")]
    return " ".join(words[:6]).title() if words else None


def _extract_question(text: str) -> str | None:
    # Only lift a question the customer actually asked; nothing is invented.
    if "?" in text:
        return text.split("?", 1)[0].strip() + "?"
    return None


REGION_PATTERN = re.compile(
    r"\b(?:in|around|near|over|across|for)\s+(?:the\s+)?(?P<region>.+?)"
    r"(?=(?:\s+(?:by|before|due|with|include|including|so that|to|as|from|between|during|next"
    r" week|this week|today|tomorrow)\b)|[.,;]|$)",
    re.IGNORECASE,
)
REGION_STOP_WORDS = ("the ", "a ", "an ")
PRIORITY_ALIASES = (
    ("critical", ("critical", "highest priority")),
    ("high", ("urgent", "high", "asap", "as soon as possible")),
    ("medium", ("medium", "moderate")),
    ("routine", ("routine", "normal", "standard")),
    ("low", ("low", "low priority")),
)


def _extract_region(text: str) -> str | None:
    for match in REGION_PATTERN.finditer(text):
        candidate = match.group("region").strip(" .")
        for prefix in REGION_STOP_WORDS:
            if candidate.casefold().startswith(prefix):
                candidate = candidate[len(prefix) :]
        if candidate:
            return candidate.title()
    return None


def _extract_priority(lowered: str) -> str | None:
    for priority, terms in PRIORITY_ALIASES:
        if any(re.search(rf"\b{re.escape(term)}\b", lowered) for term in terms):
            return priority
    return None


def _extract_output_format(lowered: str) -> str | None:
    if "briefing" in lowered or "brief" in lowered:
        return "Briefing note"
    if "assessment" in lowered:
        return "Assessment"
    if "geojson" in lowered or "map" in lowered or "geospatial" in lowered:
        return "Geospatial layer"
    if "slide" in lowered or "presentation" in lowered:
        return "Slide deck"
    if "csv" in lowered or "spreadsheet" in lowered or "table" in lowered:
        return "Data table"
    if "report" in lowered:
        return "Report"
    return None


def _extract_deadline(text: str) -> str | None:
    match = re.search(
        r"\b(?:deadline(?:\s+is|:)?|needed by|due by|by|before)\s+"
        r"(?P<deadline>[A-Za-z0-9][A-Za-z0-9 ,/-]{1,60})",
        text,
        re.IGNORECASE,
    )
    if match is None:
        return None
    return _trim_clause(match.group("deadline"))


def _extract_time_window(text: str) -> tuple[str | None, str | None]:
    date_range = re.search(
        r"\bfrom\s+(?P<start>\d{4}-\d{2}-\d{2})\s+(?:to|through|until)\s+"
        r"(?P<end>\d{4}-\d{2}-\d{2})\b",
        text,
        re.IGNORECASE,
    )
    if date_range:
        return date_range.group("start"), date_range.group("end")
    lowered = text.casefold()
    for phrase in ("next week", "this week", "next month", "this month"):
        if phrase in lowered:
            return phrase, phrase
    return None, None


def _extract_success_criteria(text: str) -> str | None:
    # Prefer the customer's own words: lift the sentence that talks about
    # success so the checklist reflects what they actually asked for.
    for sentence in _sentences(text):
        cleaned = sentence.strip()
        lowered = cleaned.casefold()
        if "success" in lowered or "criteria" in lowered:
            return _normalise_sentence(cleaned)
        if "so that" in lowered:
            return _normalise_sentence(cleaned[lowered.index("so that") :])
        if lowered.startswith(("include ", "including ")):
            return _normalise_sentence(cleaned)
    return None


def _extract_known_context(text: str) -> str | None:
    if len(text) < 24:
        return None
    return text[:220]


def _is_blank(value: object) -> bool:
    return value is None or (isinstance(value, str) and value.strip() == "")


def _normalise_spaces(value: str) -> str:
    return " ".join(value.split())


def _normalise_for_scanning(value: str) -> str:
    stripped = _ZERO_WIDTH_PATTERN.sub("", value)
    return " ".join(stripped.casefold().split())


def _sentences(value: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in re.split(r"[.!?]", value) if part.strip())


def _normalise_sentence(value: str) -> str:
    cleaned = _normalise_spaces(value).strip(" .")[:220]
    return f"{cleaned[0].upper()}{cleaned[1:]}." if cleaned else ""


def _trim_clause(value: str) -> str:
    cleaned = _normalise_spaces(value).strip(" .")
    for stop in (" include ", " including ", " so that ", " with ", " for "):
        index = cleaned.casefold().find(stop)
        if index != -1:
            cleaned = cleaned[:index]
    return cleaned.strip(" .,")


def _humanise(field: str) -> str:
    return field.replace("_", " ")
