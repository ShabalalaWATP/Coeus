"""Authenticated encryption for administrator-managed integration credentials."""

import base64
import os
import secrets
from hashlib import sha256
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from coeus.core.config import Settings
from coeus.persistence.state_store import StateStore

ENVELOPE_VERSION = 1
INTEGRATION_CREDENTIAL_NAMESPACE_PREFIX = "integration_secret:"
_DERIVATION_CONTEXT = b"coeus-configuration-encryption-v1\x00"
_TEST_MASTER_KEY = "test-only-configuration-encryption-key-0001"


def integration_secret_namespace(name: str) -> str:
    """Return the isolated persistence namespace for one logical credential."""
    return f"{INTEGRATION_CREDENTIAL_NAMESPACE_PREFIX}{name}"


class EncryptedIntegrationSecretStore:
    """Persist versioned AES-256-GCM envelopes without storing the master key."""

    def __init__(self, state_store: StateStore, settings: Settings) -> None:
        master_key = _resolve_master_key(settings)
        key = sha256(_DERIVATION_CONTEXT + master_key.encode("utf-8")).digest()
        self._cipher = AESGCM(key)
        self._key_id = sha256(key).hexdigest()[:16]
        self._state_store = state_store

    def load(self, name: str) -> str | None:
        payload = self._state_store.load(integration_secret_namespace(name))
        if not payload:
            return None
        try:
            if payload.get("version") != ENVELOPE_VERSION or payload.get("key_id") != self._key_id:
                raise ValueError
            nonce = _decode(payload.get("nonce"))
            ciphertext = _decode(payload.get("ciphertext"))
            plaintext = self._cipher.decrypt(nonce, ciphertext, _associated_data(name))
            value = plaintext.decode("utf-8")
            if not value:
                raise ValueError
            return value
        except (InvalidTag, UnicodeDecodeError, ValueError, TypeError) as exc:
            raise ValueError(
                "A persisted integration credential could not be decrypted. "
                "Restore the configuration-encryption key or clear the credential."
            ) from exc

    def save(self, name: str, value: str) -> None:
        if not value:
            raise ValueError("Integration credentials cannot be empty.")
        nonce = os.urandom(12)
        ciphertext = self._cipher.encrypt(nonce, value.encode("utf-8"), _associated_data(name))
        self._state_store.save(
            integration_secret_namespace(name),
            {
                "version": ENVELOPE_VERSION,
                "key_id": self._key_id,
                "nonce": _encode(nonce),
                "ciphertext": _encode(ciphertext),
            },
        )

    def clear(self, name: str) -> None:
        self._state_store.save(integration_secret_namespace(name), {})


def _resolve_master_key(settings: Settings) -> str:
    configured = settings.configuration_encryption_key
    if configured:
        if len(configured) < 32:
            raise ValueError("The configuration-encryption key must be at least 32 characters.")
        return configured
    if settings.environment == "test":
        return _TEST_MASTER_KEY
    if settings.environment != "local":
        raise ValueError("A configuration-encryption key is required in hosted environments.")
    return _load_or_create_local_key(Path(settings.configuration_encryption_key_path))


def _load_or_create_local_key(path: Path) -> str:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        return _read_local_key(path)
    value = secrets.token_urlsafe(48)
    with os.fdopen(descriptor, "w", encoding="utf-8") as key_file:
        key_file.write(value)
    path.chmod(0o600)
    return value


def _read_local_key(path: Path) -> str:
    value = path.read_text(encoding="utf-8").strip()
    if len(value) < 32:
        raise ValueError("The local configuration-encryption key file is invalid.")
    return value


def _associated_data(name: str) -> bytes:
    return f"coeus-integration-secret:{name}:v{ENVELOPE_VERSION}".encode()


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _decode(value: object) -> bytes:
    if not isinstance(value, str) or not value:
        raise ValueError
    padding = "=" * (-len(value) % 4)
    return base64.b64decode(value + padding, altchars=b"-_", validate=True)
