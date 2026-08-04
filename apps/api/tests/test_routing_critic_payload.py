"""Payload and evidence lookup guards for the routing critic worker."""

from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from coeus.domain.enums import TicketState
from coeus.services.routing_critic_outbox_handler import _by_id, _payload, _ticket

DECISION, CONTEXT, RFA, CM = uuid4(), uuid4(), uuid4(), uuid4()


def _values(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "decision_id": str(DECISION),
        "context_id": str(CONTEXT),
        "rfa_review_id": str(RFA),
        "cm_review_id": str(CM),
        "committed_state": TicketState.ANALYST_ASSIGNMENT.value,
    }
    values.update(overrides)
    return values


def test_a_complete_textual_payload_is_decoded() -> None:
    payload = _payload(_values())  # type: ignore[arg-type]

    assert payload.decision_id == DECISION
    assert payload.committed_state is TicketState.ANALYST_ASSIGNMENT


@pytest.mark.parametrize(
    "payload",
    [
        {},
        _values(extra="value"),
        {key: value for key, value in _values().items() if key != "cm_review_id"},
    ],
)
def test_an_unexpected_payload_shape_is_refused(payload: dict[str, object]) -> None:
    with pytest.raises(ValueError, match="Invalid routing critique payload"):
        _payload(payload)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "overrides",
    [
        {"decision_id": 7},
        {"decision_id": "not-a-uuid"},
        {"committed_state": "NOT_A_STATE"},
    ],
)
def test_a_payload_value_that_cannot_be_decoded_is_refused(
    overrides: dict[str, object],
) -> None:
    with pytest.raises(ValueError, match="Invalid routing critique payload"):
        _payload(_values(**overrides))  # type: ignore[arg-type]


def test_a_ticket_outside_the_assignment_snapshot_is_reported_as_missing() -> None:
    ticket_id = uuid4()
    tickets = SimpleNamespace(
        tickets=SimpleNamespace(assignment_snapshot=lambda: (SimpleNamespace(ticket_id=ticket_id),))
    )

    assert _ticket(tickets, ticket_id).ticket_id == ticket_id  # type: ignore[arg-type]
    with pytest.raises(LookupError, match="ticket was not found"):
        _ticket(tickets, uuid4())  # type: ignore[arg-type]


def test_missing_linked_evidence_is_reported_rather_than_guessed() -> None:
    values = (SimpleNamespace(review_id=RFA),)

    assert _by_id(values, "review_id", RFA).review_id == RFA
    with pytest.raises(LookupError, match="evidence was not found"):
        _by_id(values, "review_id", uuid4())


def test_decoding_keeps_every_identifier_distinct() -> None:
    payload = _payload(_values())  # type: ignore[arg-type]

    identifiers: set[UUID] = {
        payload.decision_id,
        payload.context_id,
        payload.rfa_review_id,
        payload.cm_review_id,
    }
    assert len(identifiers) == 4
