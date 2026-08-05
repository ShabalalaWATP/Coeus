"""Single-process authority boundary for mutable workforce decisions.

The supported local runtime is one application process. This lock prevents
assignment decisions from interleaving with roster, calendar or account
authority changes inside that process. Cross-process enforcement belongs to
the later PostgreSQL reservation phase.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from threading import RLock


class WorkforceAuthority:
    def __init__(self) -> None:
        self._lock = RLock()

    @contextmanager
    def locked(self) -> Iterator[None]:
        """Acquire the outermost workforce lock before repository locks."""
        with self._lock:
            yield


PROCESS_WORKFORCE_AUTHORITY = WorkforceAuthority()
