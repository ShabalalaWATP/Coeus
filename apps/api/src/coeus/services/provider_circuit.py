"""Thread-safe circuit breaker for remote provider acquisition."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from threading import RLock

from coeus.services.admission_metrics import AdmissionMetrics


class ProviderCircuitBreaker:
    def __init__(
        self,
        *,
        failure_threshold: int,
        cooldown_seconds: int,
        clock: Callable[[], datetime] | None = None,
        metrics: AdmissionMetrics | None = None,
    ) -> None:
        if failure_threshold < 1 or cooldown_seconds < 1:
            raise ValueError("Circuit threshold and cooldown must be positive.")
        self._failure_threshold = failure_threshold
        self._cooldown = timedelta(seconds=cooldown_seconds)
        self._clock = clock or (lambda: datetime.now(UTC))
        self._metrics = metrics or AdmissionMetrics()
        self._failures = 0
        self._opened_at: datetime | None = None
        self._probe_in_flight = False
        self._lock = RLock()

    def can_attempt(self) -> bool:
        with self._lock:
            return self._opened_at is None or self._clock() - self._opened_at >= self._cooldown

    def try_acquire(self) -> bool:
        with self._lock:
            if self._opened_at is None:
                return True
            if self._clock() - self._opened_at < self._cooldown or self._probe_in_flight:
                self._metrics.record("provider_circuit", "rejected")
                return False
            self._probe_in_flight = True
            self._metrics.record("provider_circuit", "probe")
            return True

    def record_success(self) -> None:
        with self._lock:
            self._failures = 0
            self._opened_at = None
            self._probe_in_flight = False
            self._metrics.record("provider_circuit", "success")

    def record_failure(self) -> None:
        with self._lock:
            self._failures += 1
            self._probe_in_flight = False
            if self._opened_at is not None or self._failures >= self._failure_threshold:
                self._opened_at = self._clock()
                self._metrics.record("provider_circuit", "opened")
            else:
                self._metrics.record("provider_circuit", "failure")

    def metrics_snapshot(self) -> dict[str, int]:
        return self._metrics.snapshot()
