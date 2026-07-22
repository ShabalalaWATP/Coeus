"""Strict JSON helpers for security-sensitive provider boundaries."""

import json

MAX_STRICT_JSON_NESTING = 32


def load_unique_json(raw: str) -> object:
    """Parse shallow JSON while rejecting duplicate object keys at every depth."""
    _reject_excessive_nesting(raw)
    try:
        return json.loads(raw, object_pairs_hook=_unique_object)
    except RecursionError as exc:
        raise ValueError("JSON nesting exceeds the supported limit") from exc


def _reject_excessive_nesting(raw: str) -> None:
    depth = 0
    in_string = False
    escaped = False
    for character in raw:
        if in_string:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            continue
        if character == '"':
            in_string = True
        elif character in "[{":
            depth += 1
            if depth > MAX_STRICT_JSON_NESTING:
                raise ValueError("JSON nesting exceeds the supported limit")
        elif character in "]}":
            depth = max(0, depth - 1)


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate JSON key")
        value[key] = item
    return value
