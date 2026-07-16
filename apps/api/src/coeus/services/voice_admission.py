"""Short-lived admission leases for operator-funded Realtime voice sessions."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from threading import RLock
from uuid import UUID, uuid4

from coeus.core.errors import AppError


class VoiceSessionAdmission:
    """Bound active voice sessions per process and authenticated principal."""

    def __init__(
        self,
        *,
        max_concurrent: int,
        max_per_principal: int,
        ttl_seconds: int,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._max_concurrent = max_concurrent
        self._max_per_principal = max_per_principal
        self._ttl = timedelta(seconds=ttl_seconds)
        self._clock = clock or (lambda: datetime.now(UTC))
        self._leases: dict[UUID, tuple[UUID, datetime]] = {}
        self._lock = RLock()

    def acquire(self, principal_id: UUID) -> UUID:
        with self._lock:
            self._prune()
            principal_active = sum(
                lease_principal == principal_id
                for lease_principal, _expires_at in self._leases.values()
            )
            if (
                len(self._leases) >= self._max_concurrent
                or principal_active >= self._max_per_principal
            ):
                raise AppError(
                    429,
                    "voice_session_capacity_exhausted",
                    "Voice session capacity is temporarily unavailable.",
                )
            token = uuid4()
            self._leases[token] = (principal_id, self._clock() + self._ttl)
            return token

    def release(self, principal_id: UUID, token: UUID) -> bool:
        with self._lock:
            self._prune()
            lease = self._leases.get(token)
            if lease is None or lease[0] != principal_id:
                return False
            self._leases.pop(token)
            return True

    def _prune(self) -> None:
        now = self._clock()
        expired = [token for token, (_principal, expiry) in self._leases.items() if expiry <= now]
        for token in expired:
            self._leases.pop(token)
