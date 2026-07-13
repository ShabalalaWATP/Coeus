from dataclasses import replace
from uuid import uuid4

import pytest

from coeus.core.errors import AppError
from coeus.domain.admission import AdmissionMode
from coeus.domain.enums import TicketState
from coeus.domain.tickets import IntakeDetails, TicketRecord
from coeus.persistence.state_store import PostgresStateStore
from coeus.repositories.tickets import InMemoryTicketRepository
from coeus.services.postgres_ticket_admission import PostgresTicketAdmissionController

pytestmark = pytest.mark.postgres


def _controller(database_url: str, *, total: int = 2) -> PostgresTicketAdmissionController:
    return PostgresTicketAdmissionController(
        database_url,
        max_retained=total,
        max_retained_per_principal=1,
    )


def test_two_instances_share_pending_quota_and_allocate_unique_references(
    postgres_database_url: str,
) -> None:
    PostgresStateStore(postgres_database_url, "relational").load_ticket_state()
    first = _controller(postgres_database_url)
    second = _controller(postgres_database_url)

    with first.reserve(uuid4()) as first_reference, second.reserve(uuid4()) as second_reference:
        assert first_reference == "TCK-0001"
        assert second_reference == "TCK-0002"
        with pytest.raises(AppError, match="Ticket capacity"), second.reserve(uuid4()):
            pass


@pytest.mark.parametrize(
    "terminal_state",
    [
        TicketState.CANCELLED,
        TicketState.CLOSED_DELIVERED,
        TicketState.CLOSED_EXISTING_PRODUCT_ACCEPTED,
    ],
)
def test_terminal_ticket_releases_durable_principal_capacity(
    postgres_database_url: str,
    terminal_state: TicketState,
) -> None:
    store = PostgresStateStore(postgres_database_url, "relational")
    repository = InMemoryTicketRepository(store)
    principal = uuid4()
    ticket = TicketRecord(
        ticket_id=uuid4(),
        reference=repository.next_reference(),
        requester_user_id=principal,
        state=TicketState.DRAFT_INTAKE,
        intake=IntakeDetails(title="Retained quota"),
    )
    repository.save(ticket)
    controller = _controller(postgres_database_url, total=1)

    with pytest.raises(AppError, match="Ticket capacity"), controller.reserve(principal):
        pass

    repository.save_if_current(ticket, replace(ticket, state=terminal_state))
    with controller.reserve(principal) as reference:
        assert reference == "TCK-0002"


@pytest.mark.parametrize(
    ("mode", "denied"),
    [
        (AdmissionMode.OBSERVE, False),
        (AdmissionMode.DEPLOYMENT, False),
        (AdmissionMode.PRINCIPAL, True),
    ],
)
def test_postgres_ticket_modes_stage_principal_enforcement(
    postgres_database_url: str, mode: AdmissionMode, denied: bool
) -> None:
    PostgresStateStore(postgres_database_url, "relational").load_ticket_state()
    controller = PostgresTicketAdmissionController(
        postgres_database_url,
        max_retained=2,
        max_retained_per_principal=1,
        mode=mode,
    )
    principal = uuid4()
    with controller.reserve(principal):
        if denied:
            with pytest.raises(AppError), controller.reserve(principal):
                pass
        else:
            with controller.reserve(principal):
                pass
