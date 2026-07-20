"""Provider-backed Search Planner façade with no retrieval or access authority."""

from dataclasses import dataclass
from uuid import UUID

from coeus.domain.advisory_agents import (
    AdviceItemKind,
    AdvisoryAgentKind,
    AdvisoryPrompt,
    AgentAdvice,
    AgentAdviceItem,
    AgentAdviceProvenance,
)
from coeus.domain.tickets import IntakeDetails
from coeus.services.bounded_advisory import BoundedAdvisoryService
from coeus.services.search_planner import (
    EMPTY_SEARCH_PLANNER_ADVICE,
    SEARCH_PLANNER_CONTEXT_SCHEMA_VERSION,
    SEARCH_PLANNER_PROMPT_VERSION,
    SearchPlannerAdvice,
    search_planner_prompt,
    validate_search_planner_advice,
)

SEARCH_PLANNER_POLICY_VERSION = "search-query-admission-v1"
_ITEM_KIND = {
    "query_expansions": AdviceItemKind.QUERY_EXPANSION,
    "entities": AdviceItemKind.ENTITY,
    "date_interpretations": AdviceItemKind.DATE_INTERPRETATION,
    "alternative_terminology": AdviceItemKind.ALTERNATIVE_TERMINOLOGY,
}


@dataclass(frozen=True)
class SearchPlan:
    suggestions: SearchPlannerAdvice
    record: AgentAdvice


class SearchPlannerAgent:
    def __init__(self, advisory: BoundedAdvisoryService) -> None:
        self._advisory = advisory

    def plan(self, requester_id: UUID, intake: IntakeDetails) -> SearchPlan:
        prepared = search_planner_prompt(intake)
        prompt = AdvisoryPrompt(
            data=prepared.data,
            instructions=prepared.instructions,
            prompt_version=SEARCH_PLANNER_PROMPT_VERSION,
            policy_version=SEARCH_PLANNER_POLICY_VERSION,
            context_schema_version=SEARCH_PLANNER_CONTEXT_SCHEMA_VERSION,
            max_output_tokens=512,
        )
        record = self._advisory.advise(
            agent=AdvisoryAgentKind.SEARCH_PLANNER,
            requester_id=requester_id,
            prompt=prompt,
            fallback_items=(),
            parser=_parse_items,
        )
        return SearchPlan(_advice_from_items(record.items), record)

    def plan_safely(self, requester_id: UUID, intake: IntakeDetails) -> SearchPlan:
        """Contain every advisory failure so authorised baseline retrieval still completes."""
        try:
            return self.plan(requester_id, intake)
        except Exception as error:
            provenance = AgentAdviceProvenance(
                provider_attempted=False,
                provider_succeeded=False,
                outcome="planner_error_fallback",
                provider=None,
                model=None,
                duration_ms=None,
                fallback_outcome="deterministic",
                validation_outcome="not_run",
                prompt_version=SEARCH_PLANNER_PROMPT_VERSION,
                policy_version=SEARCH_PLANNER_POLICY_VERSION,
                context_schema_version=SEARCH_PLANNER_CONTEXT_SCHEMA_VERSION,
                error_class=type(error).__name__,
            )
            return SearchPlan(
                EMPTY_SEARCH_PLANNER_ADVICE,
                AgentAdvice(AdvisoryAgentKind.SEARCH_PLANNER, (), provenance),
            )


def _parse_items(raw: str) -> tuple[AgentAdviceItem, ...]:
    return _items_from_advice(validate_search_planner_advice(raw))


def _items_from_advice(advice: SearchPlannerAdvice) -> tuple[AgentAdviceItem, ...]:
    items: list[AgentAdviceItem] = []
    for field, kind in _ITEM_KIND.items():
        for index, value in enumerate(getattr(advice, field), start=1):
            items.append(
                AgentAdviceItem(
                    kind=kind,
                    code=f"{kind.value}_{index}",
                    detail=value,
                )
            )
    return tuple(items)


def _advice_from_items(items: tuple[AgentAdviceItem, ...]) -> SearchPlannerAdvice:
    grouped = {
        field: tuple(item.detail for item in items if item.kind is kind)
        for field, kind in _ITEM_KIND.items()
    }
    return SearchPlannerAdvice(**grouped)
