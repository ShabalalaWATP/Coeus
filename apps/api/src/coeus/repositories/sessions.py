"""Bounded authenticated-session persistence."""

from datetime import UTC, datetime
from threading import RLock
from uuid import UUID

from coeus.domain.auth import SessionRecord
from coeus.persistence.codec import decode_value, encode_value
from coeus.persistence.state_store import StateStore


class SessionStoreFull(RuntimeError):
    """Raised when a new session would exceed the deployment-wide limit."""


class SessionRepository:
    def __init__(
        self,
        state_store: StateStore | None = None,
        *,
        max_per_user: int = 5,
        max_entries: int = 1_000,
    ) -> None:
        if max_per_user < 1 or max_entries < 1 or max_per_user > max_entries:
            raise ValueError("Session limits must be positive and per-user cannot exceed total.")
        self._state_store = state_store
        self._max_per_user = max_per_user
        self._max_entries = max_entries
        self._lock = RLock()
        self._sessions: dict[str, SessionRecord] = {}
        self._restore_or_persist()

    def save(self, session: SessionRecord) -> tuple[SessionRecord, ...]:
        """Admit one session while atomically enforcing retention limits."""
        with self._lock:
            sessions = dict(self._sessions)
            try:
                removed = self._prepare_admission(session)
                self._sessions[session.session_id] = session
                self._persist()
            except Exception:
                self._sessions = sessions
                raise
            return removed

    @property
    def entry_count(self) -> int:
        with self._lock:
            return len(self._sessions)

    def get(self, session_id: str) -> SessionRecord | None:
        with self._lock:
            return self._sessions.get(session_id)

    def delete(self, session_id: str) -> SessionRecord | None:
        with self._lock:
            sessions = dict(self._sessions)
            deleted = self._sessions.pop(session_id, None)
            if deleted is None:
                return None
            try:
                self._persist()
            except Exception:
                self._sessions = sessions
                raise
            return deleted

    def replace_if_current(self, expected_id: str, replacement: SessionRecord) -> bool:
        """Atomically replace one active session without reviving a stale token."""
        with self._lock:
            current = self._sessions.get(expected_id)
            if current is None or current.user_id != replacement.user_id:
                return False
            if replacement.session_id != expected_id and replacement.session_id in self._sessions:
                return False
            sessions = dict(self._sessions)
            self._sessions.pop(expected_id)
            self._sessions[replacement.session_id] = replacement
            try:
                self._persist()
            except Exception:
                self._sessions = sessions
                raise
            return True

    def delete_for_user(self, user_id: UUID) -> tuple[SessionRecord, ...]:
        with self._lock:
            sessions = dict(self._sessions)
            deleted = tuple(
                session for session in self._sessions.values() if session.user_id == user_id
            )
            if not deleted:
                return ()
            for session in deleted:
                self._sessions.pop(session.session_id, None)
            try:
                self._persist()
            except Exception:
                self._sessions = sessions
                raise
            return deleted

    def _restore_or_persist(self) -> None:
        if self._state_store is None:
            return
        payload = self._state_store.load("sessions")
        if payload is None:
            self._persist()
            return
        sessions = tuple(decode_value(item) for item in payload.get("sessions", []))
        self._sessions = {session.session_id: session for session in sessions}
        self._normalise_restored()
        self._persist()

    def _prepare_admission(self, session: SessionRecord) -> tuple[SessionRecord, ...]:
        now = datetime.now(UTC)
        removed: list[SessionRecord] = []
        for session_id, existing in tuple(self._sessions.items()):
            if existing.expires_at <= now and session_id != session.session_id:
                removed.append(self._sessions.pop(session_id))
        same_user = sorted(
            (
                item
                for item in self._sessions.values()
                if item.user_id == session.user_id and item.session_id != session.session_id
            ),
            key=lambda item: item.created_at,
        )
        while len(same_user) >= self._max_per_user:
            oldest = same_user.pop(0)
            removed.append(self._sessions.pop(oldest.session_id))
        is_new = session.session_id not in self._sessions
        if is_new and len(self._sessions) >= self._max_entries:
            raise SessionStoreFull("Session capacity is unavailable.")
        return tuple(removed)

    def _normalise_restored(self) -> None:
        now = datetime.now(UTC)
        accepted: dict[str, SessionRecord] = {}
        per_user: dict[UUID, int] = {}
        newest_first = sorted(
            self._sessions.values(), key=lambda session: session.created_at, reverse=True
        )
        for session in newest_first:
            if session.expires_at <= now or len(accepted) >= self._max_entries:
                continue
            retained = per_user.get(session.user_id, 0)
            if retained >= self._max_per_user:
                continue
            accepted[session.session_id] = session
            per_user[session.user_id] = retained + 1
        self._sessions = accepted

    def _persist(self) -> None:
        if self._state_store is None:
            return
        sessions = sorted(self._sessions.values(), key=lambda session: session.created_at)
        self._state_store.save(
            "sessions",
            {"sessions": [encode_value(session) for session in sessions]},
        )
