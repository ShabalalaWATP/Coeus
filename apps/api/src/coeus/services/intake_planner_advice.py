"""Application-owned rendering and persistence mapping for intake advice."""

from coeus.domain.advisory_agents import (
    AdviceItemKind,
    AdvisoryAgentKind,
    AgentAdvice,
    AgentAdviceItem,
    AgentAdviceProvenance,
)
from coeus.domain.tickets import IntakeDetails
from coeus.services.intake_planner_types import (
    IntakePlanDraft,
    IntakePlannerAction,
    IntakePlannerReason,
)
from coeus.services.intake_standard import (
    INTAKE_STANDARD,
    applicable_entries,
    entry_satisfied,
    next_elicitation,
)

_ACKNOWLEDGEMENTS = (
    "Got it.",
    "Thanks, that helps.",
    "Understood.",
    "Noted, thank you.",
)

_REASON_DETAILS = {
    IntakePlannerReason.DATE_WINDOW_REVERSED: "The supplied time window may run backwards.",
    IntakePlannerReason.INVALID_START_DATE: "The supplied start date may be invalid.",
    IntakePlannerReason.INVALID_END_DATE: "The supplied end date may be invalid.",
    IntakePlannerReason.BROAD_GEOGRAPHY: "The geographic scope may be too broad.",
    IntakePlannerReason.VAGUE_DATE_WORDING: "The requested time period may be ambiguous.",
    IntakePlannerReason.COMPOUND_OPERATIONAL_QUESTION: (
        "The operational question may contain multiple questions."
    ),
    IntakePlannerReason.MISSING_REQUIRED_FIELD: "A required intake field is still missing.",
    IntakePlannerReason.INTAKE_COMPLETE: "The deterministic intake checklist is complete.",
}

_FOLLOW_UP_QUESTIONS = {
    IntakePlannerReason.DATE_WINDOW_REVERSED: (
        "The start date is after the end date. What date range should be used?"
    ),
    IntakePlannerReason.INVALID_START_DATE: (
        "The start date is not valid. What start date should be used in YYYY-MM-DD format?"
    ),
    IntakePlannerReason.INVALID_END_DATE: (
        "The end date is not valid. What end date should be used in YYYY-MM-DD format?"
    ),
    IntakePlannerReason.BROAD_GEOGRAPHY: (
        "Which countries, areas or locations within that region matter most?"
    ),
    IntakePlannerReason.VAGUE_DATE_WORDING: (
        "What specific start and end dates should this cover?"
    ),
    IntakePlannerReason.COMPOUND_OPERATIONAL_QUESTION: (
        "Which part of that question should the analysts answer first?"
    ),
}


def render_intake_plan(plan: IntakePlanDraft, intake: IntakeDetails) -> str:
    """Render only application-owned copy; advice never supplies customer prose."""
    issues = (*plan.contradictions, *plan.ambiguities)
    if issues:
        return _FOLLOW_UP_QUESTIONS[issues[0]]
    if not intake.missing_information:
        return "Please review the details and press Submit."
    selected = (
        plan.suggested_field
        if plan.action is IntakePlannerAction.ASK_MISSING_FIELD
        and plan.suggested_field in intake.missing_information
        else None
    )
    entry = next(
        (item for item in INTAKE_STANDARD if item.field == selected),
        next_elicitation(intake.missing_information),
    )
    if entry is None:
        return "Please review the captured requirement."
    captured = sum(
        1 for item in applicable_entries(intake.priority) if entry_satisfied(item, intake)
    )
    return f"{_ACKNOWLEDGEMENTS[captured % len(_ACKNOWLEDGEMENTS)]} {entry.question}"


def intake_agent_advice(plan: IntakePlanDraft, provenance: AgentAdviceProvenance) -> AgentAdvice:
    items = [
        AgentAdviceItem(
            kind=(
                AdviceItemKind.CONTRADICTION
                if reason in plan.contradictions
                else AdviceItemKind.AMBIGUITY
                if reason in plan.ambiguities
                else AdviceItemKind.FOLLOW_UP_STRATEGY
            ),
            code=reason.value,
            detail=_REASON_DETAILS[reason],
        )
        for reason in plan.reasons
    ]
    items.append(
        AgentAdviceItem(
            kind=AdviceItemKind.FOLLOW_UP_STRATEGY,
            code=plan.action.value,
            detail=plan.strategy.value.replace("_", " ").capitalize() + ".",
            references=(plan.suggested_field,) if plan.suggested_field else (),
        )
    )
    return AgentAdvice(
        agent=AdvisoryAgentKind.INTAKE_PLANNER,
        items=tuple(items),
        provenance=provenance,
    )
