"""Low-cardinality admission outcome metrics without principal labels."""

from collections import Counter
from threading import RLock


class AdmissionMetrics:
    def __init__(self) -> None:
        self._counts: Counter[tuple[str, str]] = Counter()
        self._lock = RLock()

    def record(self, resource: str, outcome: str) -> None:
        with self._lock:
            self._counts[(resource, outcome)] += 1

    def snapshot(self) -> dict[str, int]:
        with self._lock:
            return {
                f"{resource}.{outcome}": count
                for (resource, outcome), count in sorted(self._counts.items())
            }
