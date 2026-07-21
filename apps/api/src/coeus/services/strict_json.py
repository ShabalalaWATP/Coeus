"""Strict JSON helpers for security-sensitive provider boundaries."""

import json


def load_unique_json(raw: str) -> object:
    """Parse JSON while rejecting duplicate object keys at every depth."""
    return json.loads(raw, object_pairs_hook=_unique_object)


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate JSON key")
        value[key] = item
    return value
