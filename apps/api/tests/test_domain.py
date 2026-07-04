from uuid import uuid4

from coeus.domain.enums import TicketState
from coeus.domain.events import DomainEvent
from coeus.domain.state_machine import can_transition


def test_ticket_state_machine_allows_defined_transition() -> None:
    assert can_transition(TicketState.DRAFT_INTAKE, TicketState.RFI_SEARCHING) is True


def test_ticket_state_machine_denies_undefined_transition() -> None:
    assert can_transition(TicketState.CANCELLED, TicketState.DRAFT_INTAKE) is False


def test_domain_event_factory_sets_event_fields() -> None:
    aggregate_id = uuid4()

    event = DomainEvent.create("ticket_created", aggregate_id)

    assert event.event_type == "ticket_created"
    assert event.aggregate_id == aggregate_id
    assert event.occurred_at.tzinfo is not None
