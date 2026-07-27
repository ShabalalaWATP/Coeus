"""Tests for intentional, exact-shape OpenAPI compatibility waivers."""

from copy import deepcopy
from typing import Any

from coeus.tools.openapi_compatibility_waivers import (
    CURRENT_INTERVENTION_FIELDS,
    LEGACY_INTERVENTION_FIELDS,
    allows_intervention_response_narrowing,
)


def _document(schema_name: str, fields: frozenset[str]) -> dict[str, Any]:
    return {
        "paths": {
            "/api/v1/routing/{ticket_id}/intervene": {
                "post": {
                    "responses": {
                        "200": {
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "$ref": f"#/components/schemas/{schema_name}",
                                    }
                                }
                            }
                        }
                    }
                }
            }
        },
        "components": {
            "schemas": {
                schema_name: {
                    "properties": {field: {"type": "string"} for field in fields},
                    "required": sorted(fields),
                }
            }
        },
    }


def test_intervention_waiver_accepts_only_the_exact_contract_migration() -> None:
    baseline = _document("RoutingTicketResponse", LEGACY_INTERVENTION_FIELDS)
    current = _document("JiocInterventionResponse", CURRENT_INTERVENTION_FIELDS)

    assert allows_intervention_response_narrowing(baseline, current)

    changed_baseline = deepcopy(baseline)
    changed_baseline["components"]["schemas"]["RoutingTicketResponse"]["properties"].pop("title")
    assert not allows_intervention_response_narrowing(changed_baseline, current)

    changed_current = deepcopy(current)
    changed_current["components"]["schemas"]["JiocInterventionResponse"]["properties"]["title"] = {
        "type": "string"
    }
    assert not allows_intervention_response_narrowing(baseline, changed_current)
