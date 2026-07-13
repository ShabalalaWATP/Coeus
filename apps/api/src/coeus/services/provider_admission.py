"""Tactical principal and deployment admission for operator-funded provider calls."""

from collections import defaultdict, deque
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from threading import RLock
from types import TracebackType
from typing import Literal
from uuid import UUID

from coeus.core.errors import AppError
from coeus.domain.admission import AdmissionMode, admission_denial_scope
from coeus.services.admission_metrics import AdmissionMetrics


class ProviderAdmissionController:
    """Bound concurrent and sliding-window provider work before acquisition."""

    def __init__(
        self,
        *,
        max_concurrent: int,
        max_calls_per_window: int,
        max_calls_per_principal: int,
        window_seconds: int,
        mode: AdmissionMode = AdmissionMode.PRINCIPAL,
        metrics: AdmissionMetrics | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._max_concurrent = max_concurrent
        self._max_calls_per_window = max_calls_per_window
        self._max_calls_per_principal = max_calls_per_principal
        self._window_seconds = window_seconds
        self._clock = clock or (lambda: datetime.now(UTC))
        self._mode = mode
        self._metrics = metrics or AdmissionMetrics()
        self._lock = RLock()
        self._active = 0
        self._deployment_calls: deque[datetime] = deque()
        self._principal_calls: dict[UUID, deque[datetime]] = defaultdict(deque)

    def reserve(self, principal_id: UUID) -> "ProviderReservation":
        return ProviderReservation(self, principal_id)

    def _acquire(self, principal_id: UUID) -> datetime:
        with self._lock:
            now = self._clock()
            self._prune(now)
            principal = self._principal_calls[principal_id]
            deployment_exceeded = (
                self._active >= self._max_concurrent
                or len(self._deployment_calls) >= self._max_calls_per_window
            )
            principal_exceeded = len(principal) >= self._max_calls_per_principal
            denial_scope = admission_denial_scope(
                self._mode,
                deployment_exceeded=deployment_exceeded,
                principal_exceeded=principal_exceeded,
            )
            if denial_scope:
                self._metrics.record("provider", f"denied_{denial_scope}")
                raise AppError(
                    429,
                    "provider_capacity_exhausted",
                    "Provider capacity is temporarily unavailable.",
                )
            self._metrics.record(
                "provider",
                "observed_denial" if deployment_exceeded or principal_exceeded else "admitted",
            )
            self._active += 1
            self._deployment_calls.append(now)
            principal.append(now)
            return now

    def _release(self, principal_id: UUID, admitted_at: datetime, *, committed: bool) -> None:
        with self._lock:
            self._active -= 1
            if not committed:
                self._deployment_calls.remove(admitted_at)
                principal = self._principal_calls[principal_id]
                principal.remove(admitted_at)
                if not principal:
                    self._principal_calls.pop(principal_id, None)

    def metrics_snapshot(self) -> dict[str, int]:
        return self._metrics.snapshot()

    def _prune(self, now: datetime) -> None:
        cutoff = now - timedelta(seconds=self._window_seconds)
        while self._deployment_calls and self._deployment_calls[0] <= cutoff:
            self._deployment_calls.popleft()
        for principal_id, calls in tuple(self._principal_calls.items()):
            while calls and calls[0] <= cutoff:
                calls.popleft()
            if not calls:
                self._principal_calls.pop(principal_id, None)


class ProviderReservation:
    def __init__(self, controller: ProviderAdmissionController, principal_id: UUID) -> None:
        self._controller = controller
        self._principal_id = principal_id
        self._admitted_at: datetime | None = None
        self._committed = False

    def __enter__(self) -> "ProviderReservation":
        self._admitted_at = self._controller._acquire(self._principal_id)
        return self

    def commit(self) -> None:
        self._committed = True

    def renew(self) -> None:
        if self._admitted_at is None:
            raise RuntimeError("Cannot renew an inactive provider reservation.")

    def __exit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc: BaseException | None,
        _traceback: TracebackType | None,
    ) -> Literal[False]:
        if self._admitted_at is not None:
            self._controller._release(
                self._principal_id, self._admitted_at, committed=self._committed
            )
            self._admitted_at = None
        return False
