from dataclasses import replace
from threading import Barrier, Thread
from uuid import uuid4

import pytest

from coeus.domain.enums import TicketState
from coeus.domain.tickets import IntakeDetails, TicketRecord
from coeus.repositories.tickets import InMemoryTicketRepository


def _ticket() -> TicketRecord:
    return TicketRecord(
        ticket_id=uuid4(),
        reference="TCK-0001",
        requester_user_id=uuid4(),
        state=TicketState.DRAFT_INTAKE,
        intake=IntakeDetails(),
    )


def test_confirmation_failure_restores_existing_and_absent_snapshots() -> None:
    repository = InMemoryTicketRepository()
    original = _ticket()
    repository.save(original)

    with pytest.raises(RuntimeError, match="audit unavailable"):
        repository.save_with_confirmation(
            replace(original, reference="TCK-CHANGED"),
            lambda: (_ for _ in ()).throw(RuntimeError("audit unavailable")),
        )
    assert repository.get(original.ticket_id) == original

    new_ticket = replace(original, ticket_id=uuid4(), reference="TCK-0002")
    with pytest.raises(RuntimeError, match="audit unavailable"):
        repository.save_with_confirmation(
            new_ticket,
            lambda: (_ for _ in ()).throw(RuntimeError("audit unavailable")),
        )
    assert repository.get(new_ticket.ticket_id) is None


def test_stale_compare_and_swap_is_rejected_without_mutation() -> None:
    repository = InMemoryTicketRepository()
    original = _ticket()
    repository.save(original)
    current = replace(original, reference="TCK-CURRENT")
    repository.save(current)

    assert not repository.save_if_current(original, replace(original, reference="TCK-STALE"))
    assert repository.get(original.ticket_id) == current


def test_only_one_concurrent_compare_and_swap_succeeds() -> None:
    repository = InMemoryTicketRepository()
    original = _ticket()
    repository.save(original)
    barrier = Barrier(3)
    outcomes: list[bool] = []

    def update(reference: str) -> None:
        barrier.wait()
        outcomes.append(
            repository.save_if_current(original, replace(original, reference=reference))
        )

    threads = [Thread(target=update, args=(f"TCK-WINNER-{index}",)) for index in range(2)]
    for thread in threads:
        thread.start()
    barrier.wait()
    for thread in threads:
        thread.join()

    assert sorted(outcomes) == [False, True]
