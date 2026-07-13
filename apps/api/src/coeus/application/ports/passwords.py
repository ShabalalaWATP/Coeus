"""Password hashing boundary used by application and repository code."""

from typing import Protocol


class PasswordHashPort(Protocol):
    def hash(self, credential: str) -> str: ...

    def verify(self, stored_hash: str, credential: str) -> bool: ...

    def needs_rehash(self, stored_hash: str) -> bool: ...
