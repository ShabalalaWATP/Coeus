from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import pytest

from coeus.repositories.auth import (
    AttemptStoreFull,
    IpAttemptRepository,
    LoginAttemptRepository,
)


def test_stale_login_failures_decay_outside_lockout_window() -> None:
    attempts = LoginAttemptRepository()
    stale = datetime.now(UTC) - timedelta(seconds=600)
    attempts._attempts["user@example.test"] = ((stale, stale), None)

    locked_until = attempts.record_failure("user@example.test", threshold=3, lockout_seconds=300)

    assert locked_until is None
    assert attempts.get_lockout_until("user@example.test") is None


def test_login_failures_within_window_still_trigger_lockout() -> None:
    attempts = LoginAttemptRepository()

    first = attempts.record_failure("user@example.test", threshold=2, lockout_seconds=300)
    second = attempts.record_failure("user@example.test", threshold=2, lockout_seconds=300)

    assert first is None
    assert second is not None
    assert second > datetime.now(UTC)


def test_fresh_pre_lockout_history_is_not_evicted_at_capacity() -> None:
    now = datetime.now(UTC)
    attempts = LoginAttemptRepository(max_entries=2, clock=lambda: now)
    for _index in range(4):
        assert (
            attempts.record_failure("target@example.test", threshold=5, lockout_seconds=300) is None
        )
    attempts.record_failure("filler@example.test", threshold=5, lockout_seconds=300)

    with pytest.raises(AttemptStoreFull):
        attempts.record_failure("churn@example.test", threshold=5, lockout_seconds=300)

    target = attempts.snapshot()["target@example.test"]
    assert len(target[0]) == 4
    assert attempts.record_failure(
        "TARGET@example.test", threshold=5, lockout_seconds=300
    ) == now + timedelta(seconds=300)


def test_expired_failure_history_can_be_reclaimed_at_capacity() -> None:
    current = datetime.now(UTC)
    attempts = LoginAttemptRepository(max_entries=1, clock=lambda: current)
    attempts.restore(
        {
            "expired@example.test": (
                (current - timedelta(seconds=301),),
                None,
            )
        }
    )

    attempts.record_failure("new@example.test", threshold=5, lockout_seconds=300)

    assert set(attempts.snapshot()) == {"new@example.test"}


def test_attempt_repositories_reject_zero_capacity() -> None:
    with pytest.raises(ValueError, match="max_entries"):
        LoginAttemptRepository(max_entries=0)
    with pytest.raises(ValueError, match="max_entries"):
        IpAttemptRepository(max_entries=0)


def test_source_attempt_repository_reclaims_stale_entries() -> None:
    attempts = IpAttemptRepository(max_entries=1)
    attempts._attempts["203.0.113.1"] = [datetime.now(UTC) - timedelta(seconds=301)]

    assert attempts.within_budget("203.0.113.2", max_attempts=1, window_seconds=300)
    assert set(attempts._attempts) == {"203.0.113.2"}


def test_source_attempt_budget_is_atomic_under_concurrency() -> None:
    attempts = IpAttemptRepository(max_entries=10)

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = tuple(
            pool.map(
                lambda _index: attempts.within_budget(
                    "203.0.113.8", max_attempts=5, window_seconds=300
                ),
                range(20),
            )
        )

    assert sum(results) == 5
    assert attempts.entry_count == 1


def test_missing_attempt_state_and_empty_reset_are_noops() -> None:
    attempts = LoginAttemptRepository()

    assert attempts.get_lockout_until("missing@example.test") is None
    reset = attempts.reset("missing@example.test")
    attempts.restore_reset("missing@example.test", reset)

    assert attempts.snapshot() == {}
