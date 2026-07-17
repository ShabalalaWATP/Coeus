from collections.abc import Mapping
from dataclasses import fields, is_dataclass
from datetime import datetime
from enum import StrEnum
from types import MappingProxyType
from typing import Any
from uuid import UUID

from coeus.persistence.codec_registry import (
    ENUM_IDENTITIES,
    LEGACY_TYPE_ALIASES,
    TYPE_IDENTITIES,
    build_identity_registries,
)


class CodecWriteFormat(StrEnum):
    """Persistence identity format used by a writer."""

    LEGACY = "legacy"
    STABLE = "stable"


(_TYPE_ID_BY_CLASS, _STABLE_TYPE_REGISTRY, _LEGACY_TYPE_REGISTRY) = build_identity_registries(
    TYPE_IDENTITIES
)
_LEGACY_TYPE_REGISTRY = {**_LEGACY_TYPE_REGISTRY, **LEGACY_TYPE_ALIASES}
(_ENUM_ID_BY_CLASS, _STABLE_ENUM_REGISTRY, _LEGACY_ENUM_REGISTRY) = build_identity_registries(
    ENUM_IDENTITIES
)


def encode_value(value: Any, *, write_format: CodecWriteFormat = CodecWriteFormat.STABLE) -> Any:
    if not isinstance(value, type) and is_dataclass(value):
        identity_key, identity = _encoded_identity(
            type(value), write_format, _TYPE_ID_BY_CLASS, "__type__", "__type_id__"
        )
        return {
            identity_key: identity,
            "fields": {
                field.name: encode_value(getattr(value, field.name), write_format=write_format)
                for field in fields(value)
            },
        }
    if isinstance(value, StrEnum):
        identity_key, identity = _encoded_identity(
            type(value), write_format, _ENUM_ID_BY_CLASS, "__enum__", "__enum_id__"
        )
        return {
            identity_key: identity,
            "value": value.value,
        }
    if isinstance(value, UUID):
        return {"__uuid__": str(value)}
    if isinstance(value, datetime):
        return {"__datetime__": value.isoformat()}
    if isinstance(value, frozenset):
        return {
            "__frozenset__": [
                encode_value(item, write_format=write_format) for item in sorted(value, key=str)
            ]
        }
    if isinstance(value, tuple):
        return {"__tuple__": [encode_value(item, write_format=write_format) for item in value]}
    if isinstance(value, MappingProxyType):
        return {
            "__mapping__": {
                key: encode_value(item, write_format=write_format) for key, item in value.items()
            }
        }
    if isinstance(value, dict):
        return {
            str(key): encode_value(item, write_format=write_format) for key, item in value.items()
        }
    if isinstance(value, list):
        return [encode_value(item, write_format=write_format) for item in value]
    return value


def decode_value(value: Any) -> Any:
    if isinstance(value, list):
        return _decode_items(value)
    if not isinstance(value, dict):
        return value
    if "__uuid__" in value:
        return UUID(value["__uuid__"])
    if "__datetime__" in value:
        return datetime.fromisoformat(value["__datetime__"])
    if "__frozenset__" in value:
        return frozenset(_decode_items(value["__frozenset__"]))
    if "__tuple__" in value:
        return tuple(_decode_items(value["__tuple__"]))
    if "__mapping__" in value:
        return MappingProxyType(_decode_mapping(value["__mapping__"]))
    if "__enum__" in value or "__enum_id__" in value:
        enum_type = _decoded_identity(
            value, "__enum__", "__enum_id__", _LEGACY_ENUM_REGISTRY, _STABLE_ENUM_REGISTRY
        )
        return enum_type(value["value"])
    if "__type__" in value or "__type_id__" in value:
        data_type = _decoded_identity(
            value, "__type__", "__type_id__", _LEGACY_TYPE_REGISTRY, _STABLE_TYPE_REGISTRY
        )
        field_names = {field.name for field in fields(data_type)}
        raw_fields = dict(value["fields"])
        decoded = _decode_mapping(
            {key: item for key, item in raw_fields.items() if key in field_names}
        )
        return data_type(**decoded)
    return _decode_mapping(value)


def _decode_items(values: list[Any]) -> list[Any]:
    return [decode_value(item) for item in values]


def _decode_mapping(value: dict[Any, Any]) -> dict[str, Any]:
    return {str(key): decode_value(item) for key, item in value.items()}


def _encoded_identity(
    python_type: type[Any],
    write_format: CodecWriteFormat,
    stable_ids: Mapping[type[Any], str],
    legacy_key: str,
    stable_key: str,
) -> tuple[str, str]:
    if write_format is CodecWriteFormat.STABLE:
        return stable_key, str(stable_ids[python_type])
    return legacy_key, f"{python_type.__module__}.{python_type.__name__}"


def _decoded_identity(
    value: dict[str, Any],
    legacy_key: str,
    stable_key: str,
    legacy_registry: Mapping[str, type[Any]],
    stable_registry: Mapping[str, type[Any]],
) -> type[Any]:
    if legacy_key in value and stable_key in value:
        raise ValueError("Persisted values must use exactly one identity format.")
    if stable_key in value:
        return stable_registry[str(value[stable_key])]
    return legacy_registry[str(value[legacy_key])]
