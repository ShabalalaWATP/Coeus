from uuid import uuid4

import pytest

from coeus.domain.enums import TicketState
from coeus.domain.tickets import IntakeDetails, TicketRecord
from coeus.persistence.codec import encode_value
from coeus.persistence.ticket_forward_reconciliation import (
    _validated_checkpoint,
    _validated_legacy_payload,
    reconcile_legacy_ticket_state,
)


@pytest.mark.parametrize(
    "checkpoint, message",
    [
        (None, "valid ticket rollback checkpoint"),
        ({"format_version": 2}, "valid ticket rollback checkpoint"),
        (
            {"format_version": 1, "checkpoint_id": "", "ticket_hashes": {}},
            "identity",
        ),
        (
            {"format_version": 1, "checkpoint_id": "id", "ticket_hashes": []},
            "hashes",
        ),
        (
            {
                "format_version": 1,
                "checkpoint_id": "id",
                "ticket_hashes": {"not-a-uuid": "0" * 64},
            },
            "invalid ID",
        ),
        (
            {
                "format_version": 1,
                "checkpoint_id": "id",
                "ticket_hashes": {str(uuid4()): "G" * 64},
            },
            "invalid hash",
        ),
    ],
)
def test_checkpoint_validation_fails_closed(
    checkpoint: object,
    message: str,
) -> None:
    with pytest.raises(RuntimeError, match=message):
        _validated_checkpoint(checkpoint)


@pytest.mark.parametrize(
    "payload, message",
    [
        (None, "missing or invalid"),
        ({"tickets": [], "counter": -1}, "shape"),
        ({"tickets": ["invalid"], "counter": 0}, "aggregate"),
        (
            {
                "tickets": [
                    {
                        "__type__": "legacy.identity",
                        "__type_id__": "stable-identity",
                        "fields": {},
                    }
                ],
                "counter": 0,
            },
            "aggregate",
        ),
        ({"tickets": [{"type": "str", "value": "not-a-ticket"}], "counter": 0}, "non-ticket"),
    ],
)
def test_legacy_payload_validation_fails_closed(payload: object, message: str) -> None:
    with pytest.raises(RuntimeError, match=message):
        _validated_legacy_payload(payload)


def test_legacy_payload_rejects_duplicate_ticket_ids() -> None:
    ticket = TicketRecord(
        ticket_id=uuid4(),
        reference="COEUS-2026-000001",
        requester_user_id=uuid4(),
        state=TicketState.DRAFT_INTAKE,
        intake=IntakeDetails(title="Duplicate"),
    )
    encoded = encode_value(ticket)

    with pytest.raises(RuntimeError, match="duplicate"):
        _validated_legacy_payload({"tickets": [encoded, encoded], "counter": 1})


@pytest.mark.parametrize(
    "operator, reason, message",
    [
        (" ", "reason", "non-empty"),
        ("operator", " ", "non-empty"),
        ("o" * 201, "reason", "bounded"),
        ("operator", "r" * 1001, "bounded"),
    ],
)
def test_reconciliation_requires_bounded_audit_evidence(
    operator: str,
    reason: str,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        reconcile_legacy_ticket_state("unused", operator=operator, reason=reason)
