"""Atomic tactical admission for retained ticket aggregates."""

from threading import RLock
from types import TracebackType
from typing import Literal, Protocol
from uuid import UUID

from coeus.core.errors import AppError
from coeus.domain.ticket_retention import ticket_consumes_capacity
from coeus.repositories.tickets import InMemoryTicketRepository


class TicketAdmissionController:
    def __init__(
        self,
        repository: InMemoryTicketRepository,
        *,
        max_retained: int,
        max_retained_per_principal: int,
    ) -> None:
        self._repository = repository
        self._max_retained = max_retained
        self._max_retained_per_principal = max_retained_per_principal
        self._pending: dict[UUID, int] = {}
        self._lock = RLock()

    def reserve(self, principal_id: UUID) -> "TicketReservation":
        return TicketReservation(self, principal_id)

    def _acquire(self, principal_id: UUID) -> str:
        with self._lock:
            retained = tuple(
                ticket
                for ticket in self._repository.list_tickets()
                if ticket_consumes_capacity(ticket.state)
            )
            pending_total = sum(self._pending.values())
            principal_total = sum(
                ticket.requester_user_id == principal_id for ticket in retained
            ) + self._pending.get(principal_id, 0)
            if (
                len(retained) + pending_total >= self._max_retained
                or principal_total >= self._max_retained_per_principal
            ):
                raise AppError(
                    429,
                    "ticket_capacity_exhausted",
                    "Ticket capacity is temporarily unavailable.",
                )
            self._pending[principal_id] = self._pending.get(principal_id, 0) + 1
            return self._repository.next_reference()

    def _release(self, principal_id: UUID) -> None:
        with self._lock:
            remaining = self._pending[principal_id] - 1
            if remaining:
                self._pending[principal_id] = remaining
            else:
                self._pending.pop(principal_id)


class TicketReservation:
    def __init__(self, controller: TicketAdmissionController, principal_id: UUID) -> None:
        self._controller = controller
        self._principal_id = principal_id
        self._active = False

    def __enter__(self) -> str:
        reference = self._controller._acquire(self._principal_id)
        self._active = True
        return reference

    def __exit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc: BaseException | None,
        _traceback: TracebackType | None,
    ) -> Literal[False]:
        if self._active:
            self._controller._release(self._principal_id)
            self._active = False
        return False


class TicketReservationPort(Protocol):
    def __enter__(self) -> str: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None: ...


class TicketAdmission(Protocol):
    def reserve(self, principal_id: UUID) -> TicketReservationPort: ...
