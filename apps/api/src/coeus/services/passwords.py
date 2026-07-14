from collections.abc import Iterator
from contextlib import contextmanager
from threading import BoundedSemaphore

from argon2 import PasswordHasher as ArgonPasswordHasher
from argon2 import Type
from argon2.exceptions import Argon2Error, VerifyMismatchError

from coeus.core.config import Settings
from coeus.core.errors import AppError


class PasswordHasher:
    def __init__(self, settings: Settings) -> None:
        self._capacity = BoundedSemaphore(settings.argon2_max_concurrent)
        self._hasher = ArgonPasswordHasher(
            time_cost=settings.argon2_time_cost,
            memory_cost=settings.argon2_memory_cost,
            parallelism=settings.argon2_parallelism,
            type=Type.ID,
        )

    def hash(self, credential: str) -> str:
        with self._reserve_capacity():
            return self._hasher.hash(credential)

    def verify(self, stored_hash: str, credential: str) -> bool:
        with self._reserve_capacity():
            try:
                return self._hasher.verify(stored_hash, credential)
            except (Argon2Error, VerifyMismatchError):
                return False

    def needs_rehash(self, stored_hash: str) -> bool:
        return self._hasher.check_needs_rehash(stored_hash)

    @contextmanager
    def _reserve_capacity(self) -> Iterator[None]:
        if not self._capacity.acquire(blocking=False):
            raise AppError(
                429,
                "password_capacity_exhausted",
                "Authentication capacity is unavailable. Try again later.",
            )
        try:
            yield
        finally:
            self._capacity.release()
