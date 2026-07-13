"""Focused resource-reservation port and local development implementation."""

from collections import Counter
from threading import RLock
from types import TracebackType
from typing import Literal
from uuid import UUID

from coeus.core.errors import AppError
from coeus.domain.admission import AdmissionMode, admission_denial_scope
from coeus.services.admission_metrics import AdmissionMetrics


class LocalResourceAdmissionController:
    def __init__(
        self,
        *,
        max_concurrent: int,
        max_concurrent_per_principal: int,
        max_units: int,
        mode: AdmissionMode = AdmissionMode.PRINCIPAL,
        metrics: AdmissionMetrics | None = None,
    ) -> None:
        self._max_concurrent = max_concurrent
        self._max_concurrent_per_principal = max_concurrent_per_principal
        self._max_units = max_units
        self._mode = mode
        self._metrics = metrics or AdmissionMetrics()
        self._active = 0
        self._active_units = 0
        self._principal_active: Counter[UUID] = Counter()
        self._lock = RLock()

    def reserve(self, principal_id: UUID, units: int = 1) -> "LocalResourceReservation":
        return LocalResourceReservation(self, principal_id, units)

    def _acquire(self, principal_id: UUID, units: int) -> None:
        with self._lock:
            if units < 1:
                self._metrics.record("resource", "denied_invalid")
                raise AppError(
                    429, "resource_capacity_exhausted", "Resource capacity is unavailable."
                )
            deployment_exceeded = (
                self._active >= self._max_concurrent or self._active_units + units > self._max_units
            )
            principal_exceeded = (
                self._principal_active[principal_id] >= self._max_concurrent_per_principal
            )
            denial_scope = admission_denial_scope(
                self._mode,
                deployment_exceeded=deployment_exceeded,
                principal_exceeded=principal_exceeded,
            )
            if denial_scope:
                self._metrics.record("resource", f"denied_{denial_scope}")
                raise AppError(
                    429, "resource_capacity_exhausted", "Resource capacity is unavailable."
                )
            if deployment_exceeded or principal_exceeded:
                self._metrics.record("resource", "observed_denial")
            else:
                self._metrics.record("resource", "admitted")
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

    def metrics_snapshot(self) -> dict[str, int]:
        return self._metrics.snapshot()


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

    def renew(self) -> None:
        if not self._active:
            raise RuntimeError("Cannot renew an inactive resource reservation.")

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
