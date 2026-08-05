"""Trusted work-update event and handler contracts."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from coeus.domain.outbox import OutboxMessage
from coeus.domain.work_update_events import WORK_UPDATE_REQUESTED, WorkUpdateEvent
from coeus.domain.workspace_productivity import WorkUpdateKind
from coeus.services.work_update_outbox_handler import WorkUpdateOutboxHandler


class _Projection:
    def __init__(self) -> None:
        self.calls = []

    def project(self, message, event) -> bool:
        self.calls.append((message, event))
        return True


def _message(kind: WorkUpdateKind = WorkUpdateKind.ASSIGNMENT) -> OutboxMessage:
    object_type = {
        WorkUpdateKind.CALENDAR_CONFLICT: "calendar",
        WorkUpdateKind.DELEGATION_EXPIRY: "grant",
    }.get(kind, "ticket")
    payload = {
        "schema_version": 1,
        "recipient_user_id": str(uuid4()),
        "kind": kind.value,
        "unit_id": str(uuid4()),
        "object_type": object_type,
        "object_id": str(uuid4()),
    }
    return OutboxMessage(uuid4(), uuid4(), 1, WORK_UPDATE_REQUESTED, payload, datetime.now(UTC), 0)


@pytest.mark.parametrize("kind", list(WorkUpdateKind))
def test_handler_accepts_every_allowlisted_privacy_minimised_kind(
    kind: WorkUpdateKind,
) -> None:
    projection = _Projection()
    message = _message(kind)

    WorkUpdateOutboxHandler(projection)(message)

    assert projection.calls == [(message, WorkUpdateEvent.from_payload(message.payload))]


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda item: object.__setattr__(item, "event_type", "user_supplied"), "Unexpected"),
        (lambda item: object.__setattr__(item, "aggregate_version", 0), "version"),
    ],
)
def test_handler_rejects_untrusted_event_types_and_versions(change, message: str) -> None:
    event = _message()
    change(event)
    projection = _Projection()

    with pytest.raises(ValueError, match=message):
        WorkUpdateOutboxHandler(projection)(event)

    assert projection.calls == []


@pytest.mark.parametrize(
    "mutation",
    [
        lambda payload: payload.update({"ticket_title": "hidden text"}),
        lambda payload: payload.update({"schema_version": 2}),
        lambda payload: payload.update({"object_type": "profile"}),
        lambda payload: payload.update({"recipient_user_id": "not-a-uuid"}),
        lambda payload: payload.pop("object_id"),
    ],
)
def test_payload_rejects_extra_text_unknown_versions_and_invalid_values(mutation) -> None:
    message = _message()
    mutation(message.payload)

    with pytest.raises(ValueError):
        WorkUpdateOutboxHandler(_Projection())(message)
