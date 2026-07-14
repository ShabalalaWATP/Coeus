from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest

from coeus.core.config import Settings
from coeus.core.errors import AppError
from coeus.services.passwords import PasswordHasher


def test_password_hasher_uses_argon2id_and_verifies_credentials() -> None:
    hasher = PasswordHasher(Settings(environment="test", argon2_memory_cost=8_192))

    stored_hash = hasher.hash("CoeusLocal1!")

    assert stored_hash.startswith("$argon2id$")
    assert hasher.verify(stored_hash, "CoeusLocal1!") is True
    assert hasher.verify(stored_hash, "wrong") is False
    assert hasher.needs_rehash(stored_hash) is False


def test_password_work_admission_is_shared_by_hash_and_verify(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hasher = PasswordHasher(
        Settings(
            environment="test",
            argon2_memory_cost=8_192,
            argon2_max_concurrent=1,
        )
    )
    started = Event()
    release = Event()

    class BlockingBackend:
        @staticmethod
        def verify(_stored_hash: str, _credential: str) -> bool:
            started.set()
            assert release.wait(timeout=5)
            return False

        @staticmethod
        def hash(_credential: str) -> str:
            return "synthetic-hash"

    monkeypatch.setattr(hasher, "_hasher", BlockingBackend())
    with ThreadPoolExecutor(max_workers=2) as executor:
        active = executor.submit(hasher.verify, "synthetic-hash", "wrong")
        assert started.wait(timeout=5)
        with pytest.raises(AppError) as denied:
            hasher.hash("another credential")
        release.set()
        assert active.result(timeout=5) is False

    assert denied.value.status_code == 429
    assert denied.value.code == "password_capacity_exhausted"


def test_password_work_capacity_is_released_after_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hasher = PasswordHasher(
        Settings(
            environment="test",
            argon2_memory_cost=8_192,
            argon2_max_concurrent=1,
        )
    )

    class FailingBackend:
        @staticmethod
        def hash(_credential: str) -> str:
            raise RuntimeError("synthetic Argon2 failure")

    monkeypatch.setattr(hasher, "_hasher", FailingBackend())
    with pytest.raises(RuntimeError, match="synthetic Argon2 failure"):
        hasher.hash("first credential")

    class WorkingBackend:
        @staticmethod
        def hash(_credential: str) -> str:
            return "synthetic-hash"

    monkeypatch.setattr(hasher, "_hasher", WorkingBackend())
    assert hasher.hash("second credential") == "synthetic-hash"
