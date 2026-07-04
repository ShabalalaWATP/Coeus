from argon2 import PasswordHasher as ArgonPasswordHasher
from argon2 import Type
from argon2.exceptions import Argon2Error, VerifyMismatchError

from coeus.core.config import Settings


class PasswordHasher:
    def __init__(self, settings: Settings) -> None:
        self._hasher = ArgonPasswordHasher(
            time_cost=settings.argon2_time_cost,
            memory_cost=settings.argon2_memory_cost,
            parallelism=settings.argon2_parallelism,
            type=Type.ID,
        )

    def hash(self, credential: str) -> str:
        return self._hasher.hash(credential)

    def verify(self, stored_hash: str, credential: str) -> bool:
        try:
            return self._hasher.verify(stored_hash, credential)
        except (Argon2Error, VerifyMismatchError):
            return False

    def needs_rehash(self, stored_hash: str) -> bool:
        return self._hasher.check_needs_rehash(stored_hash)
