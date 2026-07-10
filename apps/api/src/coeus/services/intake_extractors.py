"""Deterministic intake field extractors.

Every extractor is heuristic and transparent: values are lifted from what the
customer actually wrote, never invented. The four newer extractors
(disciplines, unit, operation, urgency justification) are cue-gated so that a
general message can never silently satisfy them; the assistant should ask.
"""

import re

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

DISCIPLINE_CUES = (
    ("GEOINT", ("geoint", "geospatial", "terrain", "mapping")),
    ("HUMINT", ("humint", "human source", "human sources")),
    ("IMINT", ("imint", "imagery", "satellite image", "satellite photo", "overhead image")),
    ("OSINT", ("osint", "open source", "open-source", "social media", "public reporting")),
    ("SIGINT", ("sigint", "signals", "intercept", "emitter")),
)

# The name must be genuinely capitalised (OP GREY HERON, Operation Onyx
# Talon); only the op/exercise keyword itself is case-insensitive.
OPERATION_PATTERN = re.compile(
    r"\b(?i:(?:operation|op|exercise|ex))\s+"
    r"(?P<name>[A-Z][A-Za-z'-]+(?:\s+[A-Z][A-Za-z'-]+){0,2})"
)
EXERCISE_PREFIX = re.compile(r"\b(?:exercise|ex)\s", re.IGNORECASE)

# Formations whose name follows the keyword (Carrier Strike Group Atlas)
# versus formations whose name precedes it (4th Armoured Brigade).
UNIT_NAME_AFTER = re.compile(
    r"\b(?P<kind>carrier strike group|task group|task force|field army"
    r"|air station|fusion cell)\s+(?P<name>[A-Z][\w'-]*)",
    re.IGNORECASE,
)
UNIT_NAME_BEFORE = re.compile(
    r"\b(?P<unit>(?:[\w'-]+\s+){1,3}(?:regiment|squadron|brigade|battalion))\b",
    re.IGNORECASE,
)
ON_BEHALF_PATTERN = re.compile(
    r"\bon behalf of\s+(?:the\s+)?(?P<unit>[A-Za-z0-9][\w '-]{2,60})", re.IGNORECASE
)

URGENCY_CUES = ("in support of", "due to", "ahead of", "time critical", "time-critical")


def extract_title(text: str) -> str | None:
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


def extract_question(text: str) -> str | None:
    # Only lift a question the customer actually asked; nothing is invented.
    if "?" in text:
        return text.split("?", 1)[0].strip() + "?"
    return None


def extract_region(text: str) -> str | None:
    for match in REGION_PATTERN.finditer(text):
        candidate = match.group("region").strip(" .")
        for prefix in REGION_STOP_WORDS:
            if candidate.casefold().startswith(prefix):
                candidate = candidate[len(prefix) :]
        if candidate:
            return candidate.title()
    return None


def extract_priority(lowered: str) -> str | None:
    for priority, terms in PRIORITY_ALIASES:
        if any(re.search(rf"\b{re.escape(term)}\b", lowered) for term in terms):
            return priority
    return None


def extract_output_format(lowered: str) -> str | None:
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


def extract_deadline(text: str) -> str | None:
    match = re.search(
        r"\b(?:deadline(?:\s+is|:)?|needed by|due by|by|before)\s+"
        r"(?P<deadline>[A-Za-z0-9][A-Za-z0-9 ,/-]{1,60})",
        text,
        re.IGNORECASE,
    )
    if match is None:
        return None
    return _trim_clause(match.group("deadline"))


def extract_time_window(text: str) -> tuple[str | None, str | None]:
    date_range = re.search(
        r"\bfrom\s+(?P<start>\d{4}-\d{2}-\d{2})\s+(?:to|through|until)\s+"
        r"(?P<end>\d{4}-\d{2}-\d{2})\b",
        text,
        re.IGNORECASE,
    )
    if date_range:
        return date_range.group("start"), date_range.group("end")
    lowered = text.casefold()
    for phrase in ("next week", "this week", "next month", "this month", "last month"):
        if phrase in lowered:
            return phrase, phrase
    return None, None


def extract_success_criteria(text: str) -> str | None:
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


def extract_known_context(text: str) -> str | None:
    if len(text) < 24:
        return None
    return text[:220]


def extract_disciplines(lowered: str) -> str | None:
    matched = tuple(
        discipline for discipline, cues in DISCIPLINE_CUES if any(cue in lowered for cue in cues)
    )
    return ", ".join(matched) if matched else None


def extract_operation(text: str) -> str | None:
    match = OPERATION_PATTERN.search(text)
    if match is None:
        return None
    kind = "Exercise" if EXERCISE_PREFIX.match(text, match.start()) else "Operation"
    return f"{kind} {match.group('name').title()}"


def extract_requesting_unit(text: str) -> str | None:
    behalf = ON_BEHALF_PATTERN.search(text)
    if behalf is not None:
        return _format_unit(_trim_clause(behalf.group("unit")))
    after = UNIT_NAME_AFTER.search(text)
    if after is not None:
        return _format_unit(f"{after.group('kind')} {after.group('name')}")
    before = UNIT_NAME_BEFORE.search(text)
    if before is None:
        return None
    return _format_unit(_trim_clause(before.group("unit")))


def _format_unit(value: str) -> str | None:
    cleaned = value.strip()
    if cleaned.casefold().startswith("the "):
        cleaned = cleaned[4:]
    titled = cleaned.title()
    # title() capitalises ordinal suffixes ("4Th"); put them back.
    titled = re.sub(r"\b(\d+)(St|Nd|Rd|Th)\b", lambda m: m.group(1) + m.group(2).lower(), titled)
    return titled or None


def extract_urgency_justification(text: str) -> str | None:
    for sentence in _sentences(text):
        lowered = sentence.casefold()
        if any(cue in lowered for cue in URGENCY_CUES):
            return _normalise_sentence(sentence)
        # A plain "because" only counts when the sentence is about urgency.
        if "because" in lowered and ("urgent" in lowered or "critical" in lowered):
            return _normalise_sentence(sentence)
    return None


def normalise_spaces(value: str) -> str:
    return " ".join(value.split())


def _sentences(value: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in re.split(r"[.!?]", value) if part.strip())


def _normalise_sentence(value: str) -> str:
    cleaned = normalise_spaces(value).strip(" .")[:220]
    return f"{cleaned[0].upper()}{cleaned[1:]}." if cleaned else ""


def _trim_clause(value: str) -> str:
    cleaned = normalise_spaces(value).strip(" .")
    for stop in (" include ", " including ", " so that ", " with ", " for "):
        index = cleaned.casefold().find(stop)
        if index != -1:
            cleaned = cleaned[:index]
    return cleaned.strip(" .,")
