"""Focused resource-reservation port and local development implementation."""

from collections import Counter
from threading import RLock
from types import TracebackType
from typing import Literal, Protocol
from uuid import UUID

from coeus.core.errors import AppError


class ResourceReservation(Protocol):
    def __enter__(self) -> None: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None: ...


class ResourceAdmission(Protocol):
    def reserve(self, principal_id: UUID, units: int = 1) -> ResourceReservation: ...


class LocalResourceAdmissionController:
    def __init__(
        self,
        *,
        max_concurrent: int,
        max_concurrent_per_principal: int,
        max_units: int,
    ) -> None:
        self._max_concurrent = max_concurrent
        self._max_concurrent_per_principal = max_concurrent_per_principal
        self._max_units = max_units
        self._active = 0
        self._active_units = 0
        self._principal_active: Counter[UUID] = Counter()
        self._lock = RLock()

    def reserve(self, principal_id: UUID, units: int = 1) -> "LocalResourceReservation":
        return LocalResourceReservation(self, principal_id, units)

    def _acquire(self, principal_id: UUID, units: int) -> None:
        with self._lock:
            if (
                units < 1
                or self._active >= self._max_concurrent
                or self._principal_active[principal_id] >= self._max_concurrent_per_principal
                or self._active_units + units > self._max_units
            ):
                raise AppError(
                    429, "resource_capacity_exhausted", "Resource capacity is unavailable."
                )
            self._active += 1
            self._active_units += units
            self._principal_active[principal_id] += 1

    def _release(self, principal_id: UUID, units: int) -> None:
        with self._lock:
            self._active -= 1
            self._active_units -= units
            self._principal_active[principal_id] -= 1
            if not self._principal_active[principal_id]:
                del self._principal_active[principal_id]


class LocalResourceReservation:
    def __init__(
        self, controller: LocalResourceAdmissionController, principal_id: UUID, units: int
    ) -> None:
        self._controller = controller
        self._principal_id = principal_id
        self._units = units
        self._active = False

    def __enter__(self) -> None:
        self._controller._acquire(self._principal_id, self._units)
        self._active = True

    def __exit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc: BaseException | None,
        _traceback: TracebackType | None,
    ) -> Literal[False]:
        if self._active:
            self._controller._release(self._principal_id, self._units)
            self._active = False
        return False
