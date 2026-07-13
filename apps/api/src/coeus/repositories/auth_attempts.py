"""Bounded, in-memory authentication-attempt repositories."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from threading import RLock


class AttemptStoreFull(RuntimeError):
    """Raised when the bounded username attempt store cannot evict entries."""


LoginAttemptState = tuple[tuple[datetime, ...], datetime | None]


@dataclass(frozen=True)
class LoginAttemptReset:
    previous: LoginAttemptState | None
    version: int


class LoginAttemptRepository:
    """Bounded username failures with version-fenced rollback."""

    def __init__(
        self,
        max_entries: int = 10_000,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if max_entries < 1:
            raise ValueError("Login attempt max_entries must be at least 1.")
        self._max_entries = max_entries
        self._clock = clock or (lambda: datetime.now(UTC))
        self._lock = RLock()
        self._attempts: dict[str, LoginAttemptState] = {}
        self._versions: dict[str, int] = {}

    def get_lockout_until(self, username: str) -> datetime | None:
        with self._lock:
            attempts = self._attempts.get(username.casefold())
            return None if attempts is None else attempts[1]

    def active_lockout_until(self, username: str) -> datetime | None:
        """Return an active lock, atomically removing only an expired state."""
        with self._lock:
            key = username.casefold()
            attempts = self._attempts.get(key)
            if attempts is None:
                return None
            locked_until = attempts[1]
            if locked_until is not None and locked_until > self._clock():
                return locked_until
            if locked_until is not None:
                self._attempts.pop(key)
                self._versions[key] = self._versions.get(key, 0) + 1
            return None

    def record_failure(
        self, username: str, threshold: int, lockout_seconds: int
    ) -> datetime | None:
        with self._lock:
            key = username.casefold()
            now = self._clock()
            if (
                key not in self._attempts
                and len(self._attempts) >= self._max_entries
                and not self._evict_stale_attempt(now, lockout_seconds)
            ):
                raise AttemptStoreFull("Login attempt store is full.")
            moments, _locked_until = self._attempts.get(key, ((), None))
            window_start = now - timedelta(seconds=lockout_seconds)
            recent = tuple(moment for moment in moments if moment > window_start)
            recent = (*recent, now)
            locked_until = (
                now + timedelta(seconds=lockout_seconds) if len(recent) >= threshold else None
            )
            self._attempts[key] = (recent, locked_until)
            self._versions[key] = self._versions.get(key, 0) + 1
            return locked_until

    def reset(self, username: str) -> LoginAttemptReset:
        with self._lock:
            key = username.casefold()
            previous = self._attempts.pop(key, None)
            version = self._versions.get(key, 0) + 1
            self._versions[key] = version
            return LoginAttemptReset(previous=previous, version=version)

    def restore_reset(self, username: str, reset: LoginAttemptReset) -> None:
        """Restore one reset only when no concurrent mutation followed it."""
        with self._lock:
            key = username.casefold()
            if self._versions.get(key, 0) != reset.version or key in self._attempts:
                return
            if reset.previous is not None:
                self._attempts[key] = reset.previous
                self._versions[key] = reset.version + 1

    def snapshot(self) -> dict[str, LoginAttemptState]:
        with self._lock:
            return dict(self._attempts)

    def restore(self, attempts: dict[str, LoginAttemptState]) -> None:
        with self._lock:
            self._attempts = dict(attempts)
            for key in set(self._versions) | set(attempts):
                self._versions[key] = self._versions.get(key, 0) + 1

    @property
    def entry_count(self) -> int:
        with self._lock:
            return len(self._attempts)

    def _evict_stale_attempt(self, now: datetime, lockout_seconds: int) -> bool:
        window_start = now - timedelta(seconds=lockout_seconds)
        for key, (moments, locked_until) in list(self._attempts.items()):
            has_recent_failure = any(moment > window_start for moment in moments)
            has_active_lock = locked_until is not None and locked_until > now
            if not has_recent_failure and not has_active_lock:
                self._attempts.pop(key)
                return True
        return False


class IpAttemptRepository:
    """Bounded per-source sliding window for authentication attempts."""

    def __init__(
        self,
        max_entries: int = 10_000,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if max_entries < 1:
            raise ValueError("IP attempt max_entries must be at least 1.")
        self._max_entries = max_entries
        self._clock = clock or (lambda: datetime.now(UTC))
        self._lock = RLock()
        self._attempts: dict[str, list[datetime]] = {}

    def within_budget(self, source: str, max_attempts: int, window_seconds: int) -> bool:
        with self._lock:
            now = self._clock()
            window_start = now - timedelta(seconds=window_seconds)
            recent = [moment for moment in self._attempts.get(source, []) if moment > window_start]
            if source not in self._attempts:
                self._prune_stale(window_start)
                if len(self._attempts) >= self._max_entries:
                    return False
            if len(recent) >= max_attempts:
                self._attempts[source] = recent[:max_attempts]
                return False
            recent.append(now)
            self._attempts[source] = recent
            return True

    @property
    def entry_count(self) -> int:
        with self._lock:
            return len(self._attempts)

    def _prune_stale(self, window_start: datetime) -> None:
        for source, moments in list(self._attempts.items()):
            if not moments or moments[-1] <= window_start:
                self._attempts.pop(source)
