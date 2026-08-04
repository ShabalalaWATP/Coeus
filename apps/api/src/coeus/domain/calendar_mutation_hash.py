"""Stable actor-bound calendar preview hashing."""

import json
from datetime import date, datetime
from enum import StrEnum
from hashlib import sha256
from uuid import UUID

from coeus.domain.workforce_calendar import CalendarMutationRequest, CalendarMutationSnapshot


def calendar_preview_hash(
    request: CalendarMutationRequest, actor_user_id: UUID, snapshot: CalendarMutationSnapshot
) -> str:
    payload = {
        "actor_user_id": str(actor_user_id),
        "request": _serialise(request),
        "snapshot": _serialise(snapshot),
    }
    return sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _serialise(value: object) -> object:
    if isinstance(value, (UUID, date, datetime, StrEnum)):
        return str(value)
    if hasattr(value, "__dataclass_fields__"):
        return {key: _serialise(item) for key, item in vars(value).items()}
    if isinstance(value, tuple):
        return [_serialise(item) for item in value]
    return value
