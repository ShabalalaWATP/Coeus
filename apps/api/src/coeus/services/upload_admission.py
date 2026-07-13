"""Process-local tactical admission for authenticated upload work."""

from collections import Counter
from threading import RLock
from types import TracebackType
from typing import Literal
from uuid import UUID

from coeus.core.errors import AppError
from coeus.services.admission_metrics import AdmissionMetrics


class UploadAdmissionController:
    """Reserve worst-case upload capacity before multipart parsing."""

    def __init__(
        self,
        *,
        max_concurrent: int,
        max_per_user: int,
        max_inflight_bytes: int,
        metrics: AdmissionMetrics | None = None,
    ) -> None:
        self._max_concurrent = max_concurrent
        self._max_per_user = max_per_user
        self._max_inflight_bytes = max_inflight_bytes
        self._metrics = metrics or AdmissionMetrics()
        self._active_by_user: Counter[UUID] = Counter()
        self._active = 0
        self._reserved_bytes = 0
        self._lock = RLock()

    def reserve(self, user_id: UUID, requested_bytes: int = 1) -> "UploadReservation":
        return UploadReservation(self, user_id, requested_bytes)

    def _acquire(self, user_id: UUID, requested_bytes: int) -> None:
        with self._lock:
            deployment_exceeded = (
                self._active >= self._max_concurrent
                or self._reserved_bytes + requested_bytes > self._max_inflight_bytes
            )
            principal_exceeded = self._active_by_user[user_id] >= self._max_per_user
            if deployment_exceeded or principal_exceeded:
                outcome = "denied_principal" if principal_exceeded else "denied_deployment"
                self._metrics.record("upload", outcome)
                raise AppError(
                    429,
                    "upload_capacity_exceeded",
                    "Upload capacity is temporarily exhausted.",
                )
            self._active += 1
            self._active_by_user[user_id] += 1
            self._reserved_bytes += requested_bytes
            self._metrics.record("upload", "admitted")

    def metrics_snapshot(self) -> dict[str, int]:
        return self._metrics.snapshot()

    def _release(self, user_id: UUID, requested_bytes: int) -> None:
        with self._lock:
            self._active -= 1
            self._active_by_user[user_id] -= 1
            self._reserved_bytes -= requested_bytes
            if self._active_by_user[user_id] == 0:
                del self._active_by_user[user_id]


class UploadReservation:
    """Exception-safe reservation without generator context-manager mutation."""

    def __init__(
        self,
        controller: UploadAdmissionController,
        user_id: UUID,
        requested_bytes: int,
    ) -> None:
        self._controller = controller
        self._user_id = user_id
        self._requested_bytes = requested_bytes
        self._active = False

    def __enter__(self) -> None:
        self._controller._acquire(self._user_id, self._requested_bytes)
        self._active = True

    def renew(self) -> None:
        if not self._active:
            raise RuntimeError("Cannot renew an inactive upload reservation.")

    def __exit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc: BaseException | None,
        _traceback: TracebackType | None,
    ) -> Literal[False]:
        if self._active:
            self._controller._release(self._user_id, self._requested_bytes)
            self._active = False
        return False
