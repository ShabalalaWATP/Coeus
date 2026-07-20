"""Closed value objects shared by the deterministic intake planner."""

from dataclasses import dataclass
from enum import StrEnum


class IntakePlannerAction(StrEnum):
    ASK_MISSING_FIELD = "ask_missing_field"
    RESOLVE_CONTRADICTION = "resolve_contradiction"
    CLARIFY_AMBIGUITY = "clarify_ambiguity"
    CONFIRM_COMPLETE = "confirm_complete"


class IntakeFollowUpStrategy(StrEnum):
    ASK_ONE_FIELD = "ask_one_field"
    VERIFY_DATE_WINDOW = "verify_date_window"
    NARROW_GEOGRAPHY = "narrow_geography"
    BOUND_TIME_PERIOD = "bound_time_period"
    SPLIT_OPERATIONAL_QUESTION = "split_operational_question"
    REVIEW_COMPLETE = "review_complete"


class IntakePlannerReason(StrEnum):
    DATE_WINDOW_REVERSED = "date_window_reversed"
    INVALID_START_DATE = "invalid_start_date"
    INVALID_END_DATE = "invalid_end_date"
    BROAD_GEOGRAPHY = "broad_geography"
    VAGUE_DATE_WORDING = "vague_date_wording"
    COMPOUND_OPERATIONAL_QUESTION = "compound_operational_question"
    MISSING_REQUIRED_FIELD = "missing_required_field"
    INTAKE_COMPLETE = "intake_complete"


class IntakePlannerSource(StrEnum):
    DETERMINISTIC = "deterministic"
    PROVIDER = "provider"


CONTRADICTION_REASONS = frozenset(
    {
        IntakePlannerReason.DATE_WINDOW_REVERSED,
        IntakePlannerReason.INVALID_START_DATE,
        IntakePlannerReason.INVALID_END_DATE,
    }
)
AMBIGUITY_REASONS = frozenset(
    {
        IntakePlannerReason.BROAD_GEOGRAPHY,
        IntakePlannerReason.VAGUE_DATE_WORDING,
        IntakePlannerReason.COMPOUND_OPERATIONAL_QUESTION,
    }
)


@dataclass(frozen=True)
class IntakePlannerPrompt:
    """Trusted instructions and separately serialised untrusted data."""

    instructions: str
    data: str


@dataclass(frozen=True)
class IntakePlanDraft:
    """Closed-vocabulary advice for a deterministic intake controller."""

    action: IntakePlannerAction
    strategy: IntakeFollowUpStrategy
    reasons: tuple[IntakePlannerReason, ...]
    suggested_field: str | None
    source: IntakePlannerSource

    @property
    def contradictions(self) -> tuple[IntakePlannerReason, ...]:
        return tuple(reason for reason in self.reasons if reason in CONTRADICTION_REASONS)

    @property
    def ambiguities(self) -> tuple[IntakePlannerReason, ...]:
        return tuple(reason for reason in self.reasons if reason in AMBIGUITY_REASONS)
