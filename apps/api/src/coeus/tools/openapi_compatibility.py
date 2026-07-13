"""Conservative semantic compatibility checks for two OpenAPI documents."""

from collections.abc import Mapping
from typing import Any, Literal

JsonObject = Mapping[str, Any]
SchemaMode = Literal["request", "response"]
HTTP_METHODS = frozenset({"get", "put", "post", "delete", "options", "head", "patch", "trace"})


def find_breaking_changes(baseline: JsonObject, current: JsonObject) -> list[str]:
    """Return stable JSON-pointer diagnostics for backwards-incompatible changes."""

    changes: list[str] = []
    baseline_paths = _mapping(baseline.get("paths"))
    current_paths = _mapping(current.get("paths"))
    for path, baseline_path_item in baseline_paths.items():
        path_pointer = f"/paths/{_escape(path)}"
        if path not in current_paths:
            changes.append(f"{path_pointer}: path removed")
            continue
        current_path_item = _mapping(current_paths[path])
        for method, baseline_operation in _mapping(baseline_path_item).items():
            if method.lower() not in HTTP_METHODS:
                continue
            operation_pointer = f"{path_pointer}/{method}"
            if method not in current_path_item:
                changes.append(f"{operation_pointer}: operation removed")
                continue
            _compare_operation(
                _mapping(baseline_operation),
                _mapping(current_path_item[method]),
                baseline,
                current,
                operation_pointer,
                changes,
            )
    return sorted(set(changes))


def _compare_operation(
    baseline: JsonObject,
    current: JsonObject,
    baseline_document: JsonObject,
    current_document: JsonObject,
    pointer: str,
    changes: list[str],
) -> None:
    if baseline.get("operationId") != current.get("operationId"):
        changes.append(f"{pointer}/operationId: operation identifier changed")
    if baseline.get("security", []) != current.get("security", []):
        changes.append(f"{pointer}/security: security requirements changed")
    _compare_parameters(baseline, current, baseline_document, current_document, pointer, changes)
    _compare_request_body(baseline, current, baseline_document, current_document, pointer, changes)
    _compare_responses(baseline, current, baseline_document, current_document, pointer, changes)


def _compare_parameters(
    baseline: JsonObject,
    current: JsonObject,
    baseline_document: JsonObject,
    current_document: JsonObject,
    pointer: str,
    changes: list[str],
) -> None:
    baseline_parameters = {
        (str(item.get("name")), str(item.get("in"))): item
        for raw in _sequence(baseline.get("parameters"))
        if (item := _resolve_object(raw, baseline_document))
    }
    current_parameters = {
        (str(item.get("name")), str(item.get("in"))): item
        for raw in _sequence(current.get("parameters"))
        if (item := _resolve_object(raw, current_document))
    }
    for identity, baseline_parameter in baseline_parameters.items():
        name, location = identity
        parameter_pointer = f"{pointer}/parameters/{location}:{name}"
        current_parameter = current_parameters.get(identity)
        if current_parameter is None:
            changes.append(f"{parameter_pointer}: parameter removed or moved")
            continue
        if not baseline_parameter.get("required", False) and current_parameter.get(
            "required", False
        ):
            changes.append(f"{parameter_pointer}/required: optional parameter became required")
        _compare_schema(
            _mapping(baseline_parameter.get("schema")),
            _mapping(current_parameter.get("schema")),
            baseline_document,
            current_document,
            f"{parameter_pointer}/schema",
            "request",
            changes,
        )
    for identity, current_parameter in current_parameters.items():
        if identity not in baseline_parameters and current_parameter.get("required", False):
            name, location = identity
            changes.append(f"{pointer}/parameters/{location}:{name}: new required parameter")


def _compare_request_body(
    baseline: JsonObject,
    current: JsonObject,
    baseline_document: JsonObject,
    current_document: JsonObject,
    pointer: str,
    changes: list[str],
) -> None:
    baseline_body = _resolve_object(baseline.get("requestBody"), baseline_document)
    if not baseline_body:
        current_body = _resolve_object(current.get("requestBody"), current_document)
        if current_body.get("required", False):
            changes.append(f"{pointer}/requestBody: new required request body")
        return
    current_body = _resolve_object(current.get("requestBody"), current_document)
    if not current_body:
        changes.append(f"{pointer}/requestBody: request body removed")
        return
    if not baseline_body.get("required", False) and current_body.get("required", False):
        changes.append(f"{pointer}/requestBody/required: request body became required")
    _compare_content(
        baseline_body,
        current_body,
        baseline_document,
        current_document,
        f"{pointer}/requestBody/content",
        "request",
        changes,
    )


def _compare_responses(
    baseline: JsonObject,
    current: JsonObject,
    baseline_document: JsonObject,
    current_document: JsonObject,
    pointer: str,
    changes: list[str],
) -> None:
    baseline_responses = _mapping(baseline.get("responses"))
    current_responses = _mapping(current.get("responses"))
    for status, raw_response in baseline_responses.items():
        response_pointer = f"{pointer}/responses/{status}"
        if status not in current_responses:
            changes.append(f"{response_pointer}: response status removed")
            continue
        _compare_content(
            _resolve_object(raw_response, baseline_document),
            _resolve_object(current_responses[status], current_document),
            baseline_document,
            current_document,
            f"{response_pointer}/content",
            "response",
            changes,
        )


def _compare_content(
    baseline_owner: JsonObject,
    current_owner: JsonObject,
    baseline_document: JsonObject,
    current_document: JsonObject,
    pointer: str,
    mode: SchemaMode,
    changes: list[str],
) -> None:
    baseline_content = _mapping(baseline_owner.get("content"))
    current_content = _mapping(current_owner.get("content"))
    for media_type, baseline_media in baseline_content.items():
        media_pointer = f"{pointer}/{_escape(media_type)}"
        if media_type not in current_content:
            changes.append(f"{media_pointer}: media type removed")
            continue
        _compare_schema(
            _mapping(_mapping(baseline_media).get("schema")),
            _mapping(_mapping(current_content[media_type]).get("schema")),
            baseline_document,
            current_document,
            f"{media_pointer}/schema",
            mode,
            changes,
        )


def _compare_schema(
    baseline_raw: JsonObject,
    current_raw: JsonObject,
    baseline_document: JsonObject,
    current_document: JsonObject,
    pointer: str,
    mode: SchemaMode,
    changes: list[str],
) -> None:
    baseline = _resolve_object(baseline_raw, baseline_document)
    current = _resolve_object(current_raw, current_document)
    if not baseline:
        return
    if not current:
        changes.append(f"{pointer}: schema removed")
        return
    if baseline.get("$ref") != current.get("$ref"):
        changes.append(f"{pointer}/$ref: schema reference changed")
    if baseline.get("type") != current.get("type"):
        changes.append(f"{pointer}/type: schema type changed")
    for composition in ("oneOf", "anyOf", "allOf", "discriminator"):
        if baseline.get(composition) != current.get(composition):
            changes.append(f"{pointer}/{composition}: schema composition changed")
    baseline_enum = set(_sequence(baseline.get("enum")))
    current_enum = set(_sequence(current.get("enum")))
    if baseline_enum and not baseline_enum <= current_enum:
        changes.append(f"{pointer}/enum: accepted value removed")
    if baseline.get("nullable", False) and not current.get("nullable", False):
        changes.append(f"{pointer}/nullable: nullable schema became non-nullable")
    _compare_bounds(baseline, current, pointer, mode, changes)
    _compare_properties(
        baseline, current, baseline_document, current_document, pointer, mode, changes
    )
    if "items" in baseline:
        _compare_schema(
            _mapping(baseline.get("items")),
            _mapping(current.get("items")),
            baseline_document,
            current_document,
            f"{pointer}/items",
            mode,
            changes,
        )


def _compare_bounds(
    baseline: JsonObject,
    current: JsonObject,
    pointer: str,
    mode: SchemaMode,
    changes: list[str],
) -> None:
    if mode != "request":
        return
    for key in ("minimum", "minLength", "minItems"):
        if key in current and (key not in baseline or current[key] > baseline[key]):
            changes.append(f"{pointer}/{key}: lower bound increased")
    for key in ("maximum", "maxLength", "maxItems"):
        if key in current and (key not in baseline or current[key] < baseline[key]):
            changes.append(f"{pointer}/{key}: upper bound decreased")


def _compare_properties(
    baseline: JsonObject,
    current: JsonObject,
    baseline_document: JsonObject,
    current_document: JsonObject,
    pointer: str,
    mode: SchemaMode,
    changes: list[str],
) -> None:
    baseline_properties = _mapping(baseline.get("properties"))
    current_properties = _mapping(current.get("properties"))
    for name, baseline_property in baseline_properties.items():
        property_pointer = f"{pointer}/properties/{_escape(name)}"
        if name not in current_properties:
            changes.append(f"{property_pointer}: property removed")
            continue
        _compare_schema(
            _mapping(baseline_property),
            _mapping(current_properties[name]),
            baseline_document,
            current_document,
            property_pointer,
            mode,
            changes,
        )
    baseline_required = set(_sequence(baseline.get("required")))
    current_required = set(_sequence(current.get("required")))
    newly_required = current_required - baseline_required
    no_longer_required = baseline_required - current_required
    if mode == "request" and newly_required:
        changes.append(f"{pointer}/required: new required properties {sorted(newly_required)}")
    if mode == "response" and no_longer_required:
        changes.append(
            f"{pointer}/required: response properties no longer guaranteed "
            f"{sorted(no_longer_required)}"
        )
    if (
        baseline.get("additionalProperties", True) is not False
        and current.get("additionalProperties", True) is False
    ):
        changes.append(f"{pointer}/additionalProperties: additional properties became forbidden")


def _resolve_object(value: Any, document: JsonObject) -> JsonObject:
    current = _mapping(value)
    seen: set[str] = set()
    while "$ref" in current:
        reference = str(current["$ref"])
        if not reference.startswith("#/") or reference in seen:
            return current
        seen.add(reference)
        resolved: Any = document
        for token in reference[2:].split("/"):
            resolved = _mapping(resolved).get(token.replace("~1", "/").replace("~0", "~"))
        current = _mapping(resolved)
    return current


def _mapping(value: Any) -> JsonObject:
    return value if isinstance(value, Mapping) else {}


def _sequence(value: Any) -> list[Any]:
    return list(value) if isinstance(value, (list, tuple)) else []


def _escape(value: str) -> str:
    return value.replace("~", "~0").replace("/", "~1")
