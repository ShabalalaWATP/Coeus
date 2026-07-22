from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest

from coeus.domain.auth import SessionRecord
from coeus.persistence.codec import encode_value
from coeus.persistence.state_store import MemoryStateStore
from coeus.repositories.auth import SessionRepository, SessionStoreFull


def _session(
    session_id: str,
    user_id: UUID,
    created_at: datetime,
    *,
    expires_at: datetime | None = None,
) -> SessionRecord:
    return SessionRecord(
        session_id=session_id,
        user_id=user_id,
        csrf_token=f"csrf-{session_id}",
        created_at=created_at,
        expires_at=expires_at or created_at + timedelta(hours=1),
    )


def test_global_capacity_rejects_without_evicting_another_principal() -> None:
    now = datetime.now(UTC)
    first_user = uuid4()
    second_user = uuid4()
    repository = SessionRepository(max_per_user=2, max_entries=2)
    first = _session("first", first_user, now)
    second = _session("second", second_user, now + timedelta(seconds=1))
    repository.save(first)
    repository.save(second)

    with pytest.raises(SessionStoreFull):
        repository.save(_session("third", first_user, now + timedelta(seconds=2)))

    assert repository.entry_count == 2
    assert repository.get(first.session_id) == first
    assert repository.get(second.session_id) == second


def test_admission_prunes_expired_sessions_before_capacity_check() -> None:
    now = datetime.now(UTC)
    repository = SessionRepository(max_per_user=2, max_entries=2)
    expired = _session(
        "expired", uuid4(), now - timedelta(hours=2), expires_at=now - timedelta(hours=1)
    )
    active = _session("active", uuid4(), now)
    replacement = _session("replacement", uuid4(), now + timedelta(seconds=1))
    repository.save(active)
    repository.save(expired)

    removed = repository.save(replacement)

    assert removed == (expired,)
    assert repository.get(expired.session_id) is None
    assert repository.entry_count == 2


def test_restore_discards_expired_and_oldest_over_limit_sessions() -> None:
    now = datetime.now(UTC)
    first_user = uuid4()
    second_user = uuid4()
    sessions = [
        _session("old", first_user, now - timedelta(minutes=3)),
        _session("new", first_user, now - timedelta(minutes=1)),
        _session("other", second_user, now - timedelta(minutes=2)),
        _session(
            "expired",
            uuid4(),
            now - timedelta(hours=2),
            expires_at=now - timedelta(hours=1),
        ),
    ]
    store = MemoryStateStore()
    store.save("sessions", {"sessions": [encode_value(item) for item in sessions]})

    repository = SessionRepository(store, max_per_user=1, max_entries=2)

    assert repository.entry_count == 2
    assert repository.get("new") is not None
    assert repository.get("other") is not None
    assert repository.get("old") is None
    assert repository.get("expired") is None


class _FailingStore(MemoryStateStore):
    fail_saves = False

    def save(self, namespace: str, payload: dict[str, Any]) -> None:
        if self.fail_saves:
            raise RuntimeError("state store unavailable")
        super().save(namespace, payload)


def test_failed_persistence_restores_evicted_session() -> None:
    now = datetime.now(UTC)
    user_id = uuid4()
    store = _FailingStore()
    repository = SessionRepository(store, max_per_user=1, max_entries=2)
    original = _session("original", user_id, now)
    repository.save(original)
    store.fail_saves = True

    with pytest.raises(RuntimeError, match="state store unavailable"):
        repository.save(_session("replacement", user_id, now + timedelta(seconds=1)))

    assert repository.entry_count == 1
    assert repository.get("original") == original
    assert repository.get("replacement") is None


def test_concurrent_admission_never_exceeds_per_user_limit() -> None:
    now = datetime.now(UTC)
    user_id = uuid4()
    repository = SessionRepository(max_per_user=3, max_entries=20)

    with ThreadPoolExecutor(max_workers=10) as executor:
        tuple(
            executor.map(
                repository.save,
                (
                    _session(f"session-{index}", user_id, now + timedelta(seconds=index))
                    for index in range(20)
                ),
            )
        )

    assert repository.entry_count == 3
    assert all(session.user_id == user_id for session in repository._sessions.values())


@pytest.mark.parametrize("per_user,total", [(0, 1), (1, 0), (2, 1)])
def test_invalid_limits_are_rejected(per_user: int, total: int) -> None:
    with pytest.raises(ValueError, match="Session limits"):
        SessionRepository(max_per_user=per_user, max_entries=total)
