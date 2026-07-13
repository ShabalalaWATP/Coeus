from dataclasses import replace
from uuid import UUID, uuid4

import pytest

from coeus.core.errors import AppError
from coeus.domain.enums import TicketState
from coeus.domain.tickets import IntakeDetails, TicketRecord
from coeus.repositories.tickets import InMemoryTicketRepository
from coeus.services.ticket_admission import TicketAdmissionController


def _ticket(principal_id: UUID, reference: str) -> TicketRecord:
    return TicketRecord(
        ticket_id=uuid4(),
        reference=reference,
        requester_user_id=principal_id,
        state=TicketState.DRAFT_INTAKE,
        intake=IntakeDetails(),
    )


@pytest.mark.parametrize(
    "terminal_state",
    [
        TicketState.CANCELLED,
        TicketState.CLOSED_DELIVERED,
        TicketState.CLOSED_EXISTING_PRODUCT_ACCEPTED,
    ],
)
def test_ticket_admission_enforces_principal_quota_and_recovers_terminal_capacity(
    terminal_state: TicketState,
) -> None:
    repository = InMemoryTicketRepository()
    principal = uuid4()
    existing = _ticket(principal, "TCK-0001")
    repository.save(existing)
    controller = TicketAdmissionController(
        repository, max_retained=10, max_retained_per_principal=1
    )

    with pytest.raises(AppError, match="Ticket capacity"), controller.reserve(principal):
        pass

    repository.save(replace(existing, state=terminal_state))
    with controller.reserve(principal) as reference:
        assert reference == "TCK-0002"


def test_ticket_admission_counts_pending_reservations_atomically() -> None:
    repository = InMemoryTicketRepository()
    controller = TicketAdmissionController(repository, max_retained=1, max_retained_per_principal=1)

    with (
        controller.reserve(uuid4()),
        pytest.raises(AppError, match="Ticket capacity"),
        controller.reserve(uuid4()),
    ):
        pass
