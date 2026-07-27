"""Precisely bounded, temporary OpenAPI compatibility waivers."""

from collections.abc import Mapping
from typing import Any

INTERVENTION_PATH = "/api/v1/routing/{ticket_id}/intervene"
LEGACY_INTERVENTION_FIELDS = frozenset(
    {
        "advisoryRuns",
        "agentRuns",
        "clarifications",
        "cmReview",
        "jiocAgentDecision",
        "managerDecisions",
        "priority",
        "priorityAssessment",
        "reanalysisContext",
        "recommendation",
        "reference",
        "requesterUserId",
        "rfaReview",
        "state",
        "ticketId",
        "title",
        "workflowPlanUpdates",
    }
)
CURRENT_INTERVENTION_FIELDS = frozenset({"ticketId", "state", "updatedAt"})


def allows_intervention_response_narrowing(
    baseline: Mapping[str, Any], current: Mapping[str, Any]
) -> bool:
    """Allow only ADR 0043's exact legacy-to-bounded response correction."""
    return _response_shape(baseline) == (
        "#/components/schemas/RoutingTicketResponse",
        LEGACY_INTERVENTION_FIELDS,
        LEGACY_INTERVENTION_FIELDS,
    ) and _response_shape(current) == (
        "#/components/schemas/JiocInterventionResponse",
        CURRENT_INTERVENTION_FIELDS,
        CURRENT_INTERVENTION_FIELDS,
    )


def _response_shape(
    document: Mapping[str, Any],
) -> tuple[str, frozenset[str], frozenset[str]] | None:
    try:
        schema_ref = document["paths"][INTERVENTION_PATH]["post"]["responses"]["200"]["content"][
            "application/json"
        ]["schema"]["$ref"]
        schema_name = schema_ref.rsplit("/", 1)[-1]
        schema = document["components"]["schemas"][schema_name]
        return (
            schema_ref,
            frozenset(schema["properties"]),
            frozenset(schema["required"]),
        )
    except (KeyError, TypeError, AttributeError):
        return None
