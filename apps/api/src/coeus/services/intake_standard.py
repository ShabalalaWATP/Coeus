"""The Istari RFI intake standard.

Defines the minimum information a query needs before it can be submitted, and
how the assistant draws each piece out naturally. Entries are ordered by
elicitation priority: the assistant asks about the first missing applicable
entry, one question per turn. Entries marked ``required_when="urgent"`` only
apply once the customer states a critical or high priority, which is how the
urgency deep-dive happens the moment urgency is claimed.

The standard is backend machinery. Chat copy must never mention required
fields, checklists or counts; the questions carry their own motivation.
"""

from dataclasses import dataclass

from coeus.domain.tickets import IntakeDetails

URGENT_PRIORITIES = frozenset({"critical", "high"})


@dataclass(frozen=True)
class IntakeFieldStandard:
    field: str
    label: str
    # Why the field is required, used in prompts and documentation.
    rationale: str
    # The natural, self-motivating question the assistant asks the customer.
    question: str
    example: str
    # "always", or "urgent" for entries that apply only at critical/high.
    required_when: str = "always"
    # Attribute checked for satisfaction when it differs from ``field``.
    satisfied_by: str | None = None


INTAKE_STANDARD: tuple[IntakeFieldStandard, ...] = (
    IntakeFieldStandard(
        field="description",
        label="What you need",
        rationale="Analysts need a plain-language statement of the requirement.",
        question="Could you tell me a little more about what you need and the background to it?",
        example="Recent vessel activity near the North Atlantic shipping lanes.",
    ),
    IntakeFieldStandard(
        field="operational_question",
        label="Question to answer",
        rationale="A single answerable question keeps the tasking focused.",
        question=(
            "What is the specific question you would like answered? "
            "Putting it as a question helps the analysts focus the work."
        ),
        example="Which ports are seeing unusual vessel activity?",
    ),
    IntakeFieldStandard(
        field="area_or_region",
        label="Area or region",
        rationale="Geographic scope routes the request to the right coverage.",
        question="So this reaches the right team, which area or region does it concern?",
        example="The Baltic ports.",
    ),
    IntakeFieldStandard(
        field="time_period",
        label="Time period",
        rationale="The window of interest bounds the collection and analysis.",
        question=(
            "What time period should this cover? A rough window is fine, "
            "for example the last month or a pair of dates."
        ),
        example="From 2026-05-01 to 2026-06-01.",
        satisfied_by="time_period_start",
    ),
    IntakeFieldStandard(
        field="priority",
        label="Priority",
        rationale="Priority decides queueing against other live requests.",
        question="How urgent is this for you: critical, high, medium, routine or low?",
        example="Routine.",
    ),
    IntakeFieldStandard(
        field="supported_operation",
        label="Supported operation",
        rationale="Urgent work is weighed by the operation or tasking it supports.",
        question=(
            "You mentioned this is urgent. Which operation, exercise or "
            "tasking is it in support of?"
        ),
        example="Operation Harbour Sentinel.",
        required_when="urgent",
    ),
    IntakeFieldStandard(
        field="urgency_justification",
        label="Why it is urgent",
        rationale="Time-sensitive drivers justify pulling effort from other work.",
        question=(
            "What makes it time critical? It helps to know what is driving "
            "the timing and what happens if the answer arrives late."
        ),
        example="A patrol posture decision is due before the weekend.",
        required_when="urgent",
    ),
    IntakeFieldStandard(
        field="deadline",
        label="Latest useful time",
        rationale="The latest time information is of value bounds urgent tasking.",
        question="When is the latest the answer would still be useful to you?",
        example="Friday morning.",
        required_when="urgent",
    ),
    IntakeFieldStandard(
        field="requesting_unit",
        label="Requesting unit",
        rationale="The requesting unit shapes handling, releasability and queueing.",
        question="Which unit or team should this be logged against?",
        example="Carrier Strike Group Atlas.",
    ),
    IntakeFieldStandard(
        field="intelligence_disciplines",
        label="Disciplines",
        rationale="Preferred disciplines steer the request towards the right cells.",
        question=(
            "Is there a kind of intelligence that would help most, for "
            "example imagery, signals, open source or geospatial work?"
        ),
        example="IMINT, OSINT.",
    ),
    IntakeFieldStandard(
        field="required_output_format",
        label="Output format",
        rationale="The delivery format shapes how the product is produced.",
        question=(
            "How would you like the results delivered? For example a briefing "
            "note, report, assessment, slide deck, data table or map layer."
        ),
        example="A briefing note.",
    ),
    IntakeFieldStandard(
        field="customer_success_criteria",
        label="Success criteria",
        rationale="Success criteria let analysts judge when the work is done.",
        question=(
            "Last couple of things: what would a good answer need to include "
            "for it to be genuinely useful to you?"
        ),
        example="Include likely origin ports and confidence levels.",
    ),
    IntakeFieldStandard(
        field="title",
        label="Title",
        rationale="A short title identifies the request in queues and search.",
        question="And finally, what short title should this go under?",
        example="Harbour Watch.",
    ),
)

# The always-required field set, kept for compatibility with existing callers.
REQUIRED_INTAKE_FIELDS: tuple[str, ...] = tuple(
    entry.field for entry in INTAKE_STANDARD if entry.required_when == "always"
)


def is_urgent_priority(priority: str | None) -> bool:
    return (priority or "").strip().casefold() in URGENT_PRIORITIES


def applicable_entries(priority: str | None) -> tuple[IntakeFieldStandard, ...]:
    """The standard entries that apply for the stated priority."""
    if is_urgent_priority(priority):
        return INTAKE_STANDARD
    return tuple(entry for entry in INTAKE_STANDARD if entry.required_when == "always")


def entry_satisfied(entry: IntakeFieldStandard, intake: IntakeDetails) -> bool:
    value = getattr(intake, entry.satisfied_by or entry.field)
    return value is not None and not (isinstance(value, str) and value.strip() == "")


def entry_value(entry: IntakeFieldStandard, intake: IntakeDetails) -> str | None:
    value = getattr(intake, entry.satisfied_by or entry.field)
    if isinstance(value, str) and value.strip():
        return value
    return None


def next_elicitation(missing_fields: tuple[str, ...]) -> IntakeFieldStandard | None:
    """The standard entry the assistant should ask about next, if any."""
    for entry in INTAKE_STANDARD:
        if entry.field in missing_fields:
            return entry
    return None
