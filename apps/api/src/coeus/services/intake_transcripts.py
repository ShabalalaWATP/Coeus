"""Parse reviewed Realtime transcripts without trusting assistant prose as input."""

import re
from dataclasses import dataclass

VOICE_TRANSCRIPT_HEADER = "Voice drafting transcript:"


@dataclass(frozen=True)
class VoiceTurn:
    speaker: str
    text: str


@dataclass(frozen=True)
class VoiceAnswer:
    field: str | None
    text: str


_QUESTION_CLASSIFIERS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "operational_question",
        ("specific question", "question you would like answered", "question should"),
    ),
    ("area_or_region", ("area or region", "which region", "what region", "where is")),
    ("time_period", ("time period", "timeframe", "date range", "window should")),
    ("priority", ("how urgent", "what priority", "priority should")),
    (
        "supported_operation",
        ("which operation", "what operation", "exercise or tasking", "in support of"),
    ),
    (
        "urgency_justification",
        ("what makes it time critical", "driving the timing", "arrives late"),
    ),
    (
        "deadline",
        ("latest the answer", "latest useful", "when do you need", "deadline"),
    ),
    ("requesting_unit", ("which unit", "what unit", "which team", "logged against")),
    (
        "intelligence_disciplines",
        ("kind of intelligence", "imagery, signals", "open source or geospatial", "discipline"),
    ),
    (
        "required_output_format",
        ("results delivered", "how should it be delivered", "output format", "slide deck"),
    ),
    (
        "customer_success_criteria",
        ("good answer", "need to include", "genuinely useful", "success criteria"),
    ),
    ("title", ("short title", "title should", "go under", "call this request")),
    (
        "description",
        ("what you need", "background to it", "more detail about", "tell me about the query"),
    ),
)


def voice_turns(message: str) -> tuple[VoiceTurn, ...] | None:
    """Return labelled turns for the exact client voice envelope, otherwise ``None``."""
    lines = message.splitlines()
    if not lines or lines[0].strip() != VOICE_TRANSCRIPT_HEADER:
        return None
    parsed: list[VoiceTurn] = []
    for raw_line in lines[1:]:
        line = raw_line.strip()
        if not line:
            continue
        match = re.match(r"^(You|Istari):\s*(.*)$", line, re.IGNORECASE)
        if match:
            speaker = "user" if match.group(1).casefold() == "you" else "assistant"
            text = match.group(2).strip()
            if text:
                parsed.append(VoiceTurn(speaker, text))
            continue
        if parsed:
            previous = parsed[-1]
            parsed[-1] = VoiceTurn(previous.speaker, f"{previous.text} {line}")
    return tuple(parsed)


def requester_message(message: str) -> str:
    """Return only requester-authored content for lifecycle decisions."""
    turns = voice_turns(message)
    if turns is None:
        return message
    return " ".join(turn.text for turn in turns if turn.speaker == "user")


def voice_answers(turns: tuple[VoiceTurn, ...]) -> tuple[VoiceAnswer, ...]:
    """Group requester turns under the intake question that preceded them."""
    groups: list[tuple[str | None, list[str]]] = []
    current: int | None = None
    for turn in turns:
        if turn.speaker == "assistant":
            field = _classify_question(turn.text)
            if field is not None:
                groups.append((field, []))
                current = len(groups) - 1
            continue
        if current is None:
            groups.append((None, [turn.text]))
            current = len(groups) - 1
        else:
            groups[current][1].append(turn.text)
    return tuple(VoiceAnswer(field, " ".join(parts)) for field, parts in groups if any(parts))


def _classify_question(text: str) -> str | None:
    lowered = " ".join(text.casefold().split())
    for field, cues in _QUESTION_CLASSIFIERS:
        if any(cue in lowered for cue in cues):
            return field
    return None
