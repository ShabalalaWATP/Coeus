"""Application boundaries for scarce-resource admission and reservations."""

from types import TracebackType
from typing import Protocol
from uuid import UUID


class ResourceReservation(Protocol):
    def __enter__(self) -> None: ...

    def renew(self) -> None: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None: ...


class ResourceAdmission(Protocol):
    def reserve(self, principal_id: UUID, units: int = 1) -> ResourceReservation: ...


class ProviderReservation(Protocol):
    def __enter__(self) -> "ProviderReservation": ...

    def commit(self) -> None: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None: ...


class ProviderAdmission(Protocol):
    def reserve(self, principal_id: UUID) -> ProviderReservation: ...


class TicketReservation(Protocol):
    def __enter__(self) -> str: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None: ...


class TicketAdmission(Protocol):
    def reserve(self, principal_id: UUID) -> TicketReservation: ...
