"""Tests for the semantic OpenAPI compatibility gate."""

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from coeus.tools.openapi_compatibility import find_breaking_changes


def _document() -> dict[str, Any]:
    return {
        "openapi": "3.1.0",
        "paths": {
            "/items/{item_id}": {
                "get": {
                    "operationId": "get_item",
                    "parameters": [
                        {
                            "name": "item_id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"},
                        },
                        {
                            "name": "view",
                            "in": "query",
                            "required": False,
                            "schema": {"type": "string", "enum": ["summary", "full"]},
                        },
                    ],
                    "responses": {
                        "200": {
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/Item"}
                                }
                            }
                        },
                        "404": {"content": {"application/json": {"schema": {"type": "object"}}}},
                    },
                },
                "post": {
                    "operationId": "update_item",
                    "requestBody": {
                        "required": False,
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/ItemUpdate"}
                            }
                        },
                    },
                    "responses": {"204": {"description": "Updated"}},
                },
            }
        },
        "components": {
            "schemas": {
                "Item": {
                    "type": "object",
                    "required": ["id", "status"],
                    "properties": {
                        "id": {"type": "string"},
                        "status": {"type": "string", "enum": ["draft", "released"]},
                    },
                },
                "ItemUpdate": {
                    "type": "object",
                    "properties": {"title": {"type": "string", "minLength": 1, "maxLength": 100}},
                },
            }
        },
    }


def test_descriptions_and_additive_changes_are_compatible() -> None:
    baseline = _document()
    current = deepcopy(baseline)
    current["paths"]["/items/{item_id}"]["get"]["description"] = "More detail"
    current["paths"]["/items/{item_id}"]["get"]["responses"]["429"] = {"description": "Limited"}
    current["components"]["schemas"]["Item"]["properties"]["status"]["enum"].append("archived")
    current["components"]["schemas"]["Item"]["properties"]["label"] = {"type": "string"}

    assert find_breaking_changes(baseline, current) == []


@pytest.mark.parametrize(
    ("mutation", "diagnostic"),
    [
        (lambda doc: doc["paths"].pop("/items/{item_id}"), "path removed"),
        (
            lambda doc: doc["paths"]["/items/{item_id}"].pop("get"),
            "operation removed",
        ),
        (
            lambda doc: doc["paths"]["/items/{item_id}"]["get"].update({"operationId": "renamed"}),
            "operation identifier changed",
        ),
        (
            lambda doc: doc["paths"]["/items/{item_id}"]["get"]["responses"].pop("404"),
            "response status removed",
        ),
        (
            lambda doc: doc["paths"]["/items/{item_id}"]["post"]["requestBody"].update(
                {"required": True}
            ),
            "request body became required",
        ),
    ],
)
def test_operation_contract_breaks_are_reported(
    mutation: Any,
    diagnostic: str,
) -> None:
    baseline = _document()
    current = deepcopy(baseline)
    mutation(current)

    assert any(diagnostic in change for change in find_breaking_changes(baseline, current))


def test_parameter_moves_and_new_required_parameters_are_breaking() -> None:
    baseline = _document()
    current = deepcopy(baseline)
    parameters = current["paths"]["/items/{item_id}"]["get"]["parameters"]
    parameters[1]["in"] = "header"
    parameters.append(
        {
            "name": "mode",
            "in": "query",
            "required": True,
            "schema": {"type": "string"},
        }
    )

    changes = find_breaking_changes(baseline, current)

    assert any("view: parameter removed or moved" in change for change in changes)
    assert any("mode: new required parameter" in change for change in changes)


def test_request_schema_narrowing_is_breaking() -> None:
    baseline = _document()
    current = deepcopy(baseline)
    update = current["components"]["schemas"]["ItemUpdate"]
    update["required"] = ["title"]
    update["properties"]["title"]["minLength"] = 10
    update["properties"]["title"]["maxLength"] = 20

    changes = find_breaking_changes(baseline, current)

    assert any("new required properties" in change for change in changes)
    assert any("lower bound increased" in change for change in changes)
    assert any("upper bound decreased" in change for change in changes)


def test_response_schema_removal_and_weakened_guarantee_are_breaking() -> None:
    baseline = _document()
    current = deepcopy(baseline)
    item = current["components"]["schemas"]["Item"]
    item["properties"].pop("status")
    item["required"].remove("status")

    changes = find_breaking_changes(baseline, current)

    assert any("status: property removed" in change for change in changes)
    assert any("response properties no longer guaranteed" in change for change in changes)


def test_removed_enum_value_and_changed_security_are_breaking() -> None:
    baseline = _document()
    current = deepcopy(baseline)
    current["components"]["schemas"]["Item"]["properties"]["status"]["enum"] = ["draft"]
    current["paths"]["/items/{item_id}"]["get"]["security"] = [{"cookie": []}]

    changes = find_breaking_changes(baseline, current)

    assert any("accepted value removed" in change for change in changes)
    assert any("security requirements changed" in change for change in changes)


def test_optional_parameter_and_body_cannot_become_required() -> None:
    baseline = _document()
    current = deepcopy(baseline)
    current["paths"]["/items/{item_id}"]["get"]["parameters"][1]["required"] = True
    baseline["paths"]["/items/{item_id}"]["get"].pop("requestBody", None)
    current["paths"]["/items/{item_id}"]["get"]["requestBody"] = {
        "required": True,
        "content": {"application/json": {"schema": {"type": "object"}}},
    }

    changes = find_breaking_changes(baseline, current)

    assert any("optional parameter became required" in change for change in changes)
    assert any("new required request body" in change for change in changes)


def test_body_and_media_type_removal_are_breaking() -> None:
    baseline = _document()
    current = deepcopy(baseline)
    current["paths"]["/items/{item_id}"]["post"].pop("requestBody")
    current["paths"]["/items/{item_id}"]["get"]["responses"]["200"]["content"] = {}

    changes = find_breaking_changes(baseline, current)

    assert any("request body removed" in change for change in changes)
    assert any("media type removed" in change for change in changes)


def test_schema_shape_restrictions_are_breaking() -> None:
    baseline = _document()
    current = deepcopy(baseline)
    baseline_item = baseline["components"]["schemas"]["Item"]
    current_item = current["components"]["schemas"]["Item"]
    baseline_item.update(
        {
            "nullable": True,
            "additionalProperties": True,
            "items": {"type": "string"},
            "oneOf": [{"type": "object"}],
        }
    )
    current_item.update(
        {
            "type": "array",
            "nullable": False,
            "additionalProperties": False,
            "items": {},
            "oneOf": [{"type": "string"}],
        }
    )

    changes = find_breaking_changes(baseline, current)

    assert any("schema type changed" in change for change in changes)
    assert any("schema composition changed" in change for change in changes)
    assert any("nullable schema became non-nullable" in change for change in changes)
    assert any("additional properties became forbidden" in change for change in changes)
    assert any("/items: schema removed" in change for change in changes)


def test_missing_baseline_schema_and_non_http_path_metadata_are_ignored() -> None:
    baseline = _document()
    current = deepcopy(baseline)
    baseline["paths"]["/items/{item_id}"]["summary"] = "Item operations"
    current["paths"]["/items/{item_id}"]["summary"] = "Renamed summary"
    baseline["paths"]["/items/{item_id}"]["get"]["responses"]["404"]["content"]["application/json"][
        "schema"
    ] = {}
    current["paths"]["/items/{item_id}"]["get"]["responses"]["404"]["content"]["application/json"][
        "schema"
    ] = {"type": "string"}

    assert find_breaking_changes(baseline, current) == []


def test_external_and_cyclic_references_fail_conservatively() -> None:
    baseline = _document()
    current = deepcopy(baseline)
    baseline["components"]["schemas"]["Item"] = {"$ref": "external.json#/Item"}
    current["components"]["schemas"]["Item"] = {"$ref": "external.json#/Other"}

    changes = find_breaking_changes(baseline, current)

    assert any("schema reference changed" in change for change in changes)


def test_representative_api_shapes_match_committed_compatibility_fixtures() -> None:
    root = Path(__file__).parents[3]
    contract = json.loads((root / "packages/contracts/openapi.json").read_text(encoding="utf-8"))
    fixtures = json.loads(
        (root / "packages/test-fixtures/api-compatibility-shapes.json").read_text(encoding="utf-8")
    )

    for fixture in fixtures:
        operation = contract["paths"][fixture["path"]][fixture["method"]]
        media_type = fixture.get("requestMediaType")
        if media_type is not None:
            assert media_type in operation["requestBody"]["content"]
        schema = operation["responses"][fixture["status"]]["content"]["application/json"]["schema"]
        assert schema["$ref"] == f"#/components/schemas/{fixture['responseSchema']}"
