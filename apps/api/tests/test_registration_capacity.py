from concurrent.futures import ThreadPoolExecutor
from threading import Event, Lock

import pytest

from coeus.core.config import Settings
from coeus.core.errors import AppError
from coeus.repositories.auth import SeedUserRepository
from coeus.repositories.registration import RegistrationRepository
from coeus.services.audit import AuditLog
from coeus.services.passwords import PasswordHasher
from coeus.services.registration import RegistrationService


class BlockingHasher(PasswordHasher):
    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        self.started = Event()
        self.release = Event()
        self._calls_lock = Lock()
        self.calls = 0

    def hash(self, credential: str) -> str:
        with self._calls_lock:
            self.calls += 1
        self.started.set()
        assert self.release.wait(timeout=5)
        return super().hash(credential)


class FailOnceHasher(PasswordHasher):
    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        self.fail = True

    def hash(self, credential: str) -> str:
        if self.fail:
            self.fail = False
            raise RuntimeError("simulated hash failure")
        return super().hash(credential)


def test_concurrent_submissions_cannot_cross_pending_capacity() -> None:
    settings = Settings(
        environment="test",
        argon2_memory_cost=8_192,
        registration_max_pending=1,
    )
    hasher = BlockingHasher(settings)
    repository = RegistrationRepository()
    service = _service(settings, repository, hasher)

    with ThreadPoolExecutor(max_workers=8) as executor:
        accepted = executor.submit(_submit, service, "accepted@example.test")
        assert hasher.started.wait(timeout=5)
        rejected = [
            executor.submit(_submit, service, f"rejected-{index}@example.test")
            for index in range(7)
        ]
        for future in rejected:
            with pytest.raises(AppError) as raised:
                future.result(timeout=5)
            assert raised.value.code == "registration_throttled"
        hasher.release.set()
        accepted.result(timeout=5)

    assert repository.pending_count() == 1
    assert repository.reservation_count == 0
    assert hasher.calls == 1


def test_hash_failure_releases_reserved_capacity() -> None:
    settings = Settings(
        environment="test",
        argon2_memory_cost=8_192,
        registration_max_pending=1,
    )
    hasher = FailOnceHasher(settings)
    repository = RegistrationRepository()
    service = _service(settings, repository, hasher)

    with pytest.raises(RuntimeError, match="simulated hash failure"):
        _submit(service, "first@example.test")
    _submit(service, "second@example.test")

    assert repository.pending_count() == 1
    assert repository.reservation_count == 0


def _service(
    settings: Settings,
    repository: RegistrationRepository,
    hasher: PasswordHasher,
) -> RegistrationService:
    return RegistrationService(
        settings,
        SeedUserRepository(settings, PasswordHasher(settings)),
        repository,
        hasher,
        AuditLog(),
    )


def _submit(service: RegistrationService, username: str) -> None:
    service.submit(username, "Synthetic Operator", "Synthetic local duties.", "Passphrase123!")
