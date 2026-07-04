from coeus.core.config import Settings
from coeus.services.passwords import PasswordHasher


def test_password_hasher_uses_argon2id_and_verifies_credentials() -> None:
    hasher = PasswordHasher(Settings(environment="test", argon2_memory_cost=8_192))

    stored_hash = hasher.hash("CoeusLocal1!")

    assert stored_hash.startswith("$argon2id$")
    assert hasher.verify(stored_hash, "CoeusLocal1!") is True
    assert hasher.verify(stored_hash, "wrong") is False
    assert hasher.needs_rehash(stored_hash) is False
