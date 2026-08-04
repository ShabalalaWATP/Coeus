"""Stable command-result codecs used for lost-response replays."""

import json
from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from coeus.domain.workspace_productivity import (
    PackageTemplate,
    SavedBoardView,
    WorkUpdate,
    WorkUpdateKind,
)
from coeus.persistence.workspace_productivity_records import filters_json, parse_filters


def _sequence(value: object) -> Sequence[object]:
    """A replayed result must carry a list here; anything else is corrupt."""
    if not isinstance(value, Sequence) or isinstance(value, str | bytes):
        raise ValueError("package_titles is invalid")
    return value


def view_result(item: SavedBoardView) -> dict[str, object]:
    return {
        "aggregate_id": str(item.view_id),
        "owner_user_id": str(item.owner_user_id),
        "unit_id": str(item.unit_id),
        "name": item.name,
        "filters": json.loads(filters_json(item.filters)),
        "version": item.version,
        "updated_at": item.updated_at.isoformat(),
    }


def view_from_result(value: dict[str, object]) -> SavedBoardView:
    return SavedBoardView(
        UUID(str(value["aggregate_id"])),
        UUID(str(value["owner_user_id"])),
        UUID(str(value["unit_id"])),
        str(value["name"]),
        parse_filters(value["filters"]),
        int(str(value["version"])),
        datetime.fromisoformat(str(value["updated_at"])),
    )


def template_result(item: PackageTemplate) -> dict[str, object]:
    return {
        "aggregate_id": str(item.template_id),
        "unit_id": str(item.unit_id),
        "owner_user_id": str(item.owner_user_id),
        "name": item.name,
        "package_titles": list(item.package_titles),
        "estimated_minutes": item.estimated_minutes,
        "priority": item.priority,
        "version": item.version,
        "updated_at": item.updated_at.isoformat(),
    }


def template_from_result(value: dict[str, object]) -> PackageTemplate:
    return PackageTemplate(
        UUID(str(value["aggregate_id"])),
        UUID(str(value["unit_id"])),
        UUID(str(value["owner_user_id"])),
        str(value["name"]),
        tuple(str(item) for item in _sequence(value["package_titles"])),
        int(str(value["estimated_minutes"]))
        if value.get("estimated_minutes") is not None
        else None,
        int(str(value["priority"])) if value.get("priority") is not None else None,
        int(str(value["version"])),
        datetime.fromisoformat(str(value["updated_at"])),
    )


def update_result(item: WorkUpdate) -> dict[str, object]:
    return {
        "aggregate_id": str(item.update_id),
        "recipient_user_id": str(item.recipient_user_id),
        "event_key": item.event_key,
        "kind": item.kind.value,
        "unit_id": str(item.unit_id),
        "object_type": item.object_type,
        "object_id": str(item.object_id),
        "occurred_at": item.occurred_at.isoformat(),
        "acknowledged_at": item.acknowledged_at.isoformat() if item.acknowledged_at else None,
        "version": 1,
    }


def update_from_result(value: dict[str, object]) -> WorkUpdate:
    acknowledged = value.get("acknowledged_at")
    return WorkUpdate(
        UUID(str(value["aggregate_id"])),
        UUID(str(value["recipient_user_id"])),
        str(value["event_key"]),
        WorkUpdateKind(str(value["kind"])),
        UUID(str(value["unit_id"])),
        str(value["object_type"]),
        UUID(str(value["object_id"])),
        datetime.fromisoformat(str(value["occurred_at"])),
        datetime.fromisoformat(str(acknowledged)) if acknowledged else None,
    )
