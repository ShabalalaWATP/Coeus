from pathlib import Path

import pytest

from coeus.core.config import Settings
from coeus.persistence.state_store import FileStateStore, MemoryStateStore
from coeus.services.integration_secrets import (
    EncryptedIntegrationSecretStore,
    integration_secret_namespace,
)


def _settings(key: str) -> Settings:
    return Settings(environment="test", configuration_encryption_key=key)


def test_envelopes_are_randomised_authenticated_and_bound_to_the_credential() -> None:
    state = MemoryStateStore()
    secrets = EncryptedIntegrationSecretStore(state, _settings("a" * 32))
    name = "llm:openai_api"
    secrets.save(name, "sk-provider-secret")
    first = state.load(integration_secret_namespace(name))
    assert first and first["version"] == 1
    assert "sk-provider-secret" not in str(first)
    assert secrets.load(name) == "sk-provider-secret"

    secrets.save(name, "sk-provider-secret")
    second = state.load(integration_secret_namespace(name))
    assert second and second["nonce"] != first["nonce"]

    state.save(integration_secret_namespace("voice:openai_realtime"), second)
    with pytest.raises(ValueError, match="could not be decrypted"):
        secrets.load("voice:openai_realtime")


def test_tampered_malformed_and_wrong_key_envelopes_fail_closed() -> None:
    state = MemoryStateStore()
    secrets = EncryptedIntegrationSecretStore(state, _settings("a" * 32))
    name = "llm:gemini_api"
    secrets.save(name, "gemini-provider-secret")
    envelope = state.load(integration_secret_namespace(name))
    assert envelope
    envelope["ciphertext"] = f"{envelope['ciphertext']}A"
    state.save(integration_secret_namespace(name), envelope)

    with pytest.raises(ValueError, match="could not be decrypted"):
        secrets.load(name)
    with pytest.raises(ValueError, match="could not be decrypted"):
        EncryptedIntegrationSecretStore(state, _settings("b" * 32)).load(name)

    secrets.save(name, "gemini-provider-secret")
    malformed = state.load(integration_secret_namespace(name))
    assert malformed
    malformed["nonce"] = None
    state.save(integration_secret_namespace(name), malformed)
    with pytest.raises(ValueError, match="could not be decrypted"):
        secrets.load(name)


def test_invalid_configured_and_hosted_master_keys_are_rejected() -> None:
    state = MemoryStateStore()
    with pytest.raises(ValueError, match="at least 32 characters"):
        EncryptedIntegrationSecretStore(state, _settings("short"))
    with pytest.raises(ValueError, match="required in hosted environments"):
        EncryptedIntegrationSecretStore(state, Settings(environment="dev"))


def test_local_key_file_and_encrypted_file_state_survive_restart(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"
    key_path = tmp_path / "separate-secrets" / "configuration.key"
    settings = Settings(
        environment="local",
        configuration_encryption_key_path=str(key_path),
    )
    first = EncryptedIntegrationSecretStore(FileStateStore(state_path), settings)
    first.save("voice:openai_realtime", "sk-local-voice-secret")

    assert key_path.exists()
    assert "sk-local-voice-secret" not in state_path.read_text(encoding="utf-8")
    restarted = EncryptedIntegrationSecretStore(FileStateStore(state_path), settings)
    assert restarted.load("voice:openai_realtime") == "sk-local-voice-secret"


def test_invalid_existing_local_key_file_is_rejected(tmp_path: Path) -> None:
    key_path = tmp_path / "configuration.key"
    key_path.write_text("short", encoding="utf-8")
    settings = Settings(environment="local", configuration_encryption_key_path=str(key_path))

    with pytest.raises(ValueError, match="key file is invalid"):
        EncryptedIntegrationSecretStore(MemoryStateStore(), settings)


def test_empty_and_cleared_credentials_are_not_loaded() -> None:
    state = MemoryStateStore()
    secrets = EncryptedIntegrationSecretStore(state, _settings("a" * 32))
    assert secrets.load("llm:bedrock") is None
    with pytest.raises(ValueError, match="cannot be empty"):
        secrets.save("llm:bedrock", "")
    secrets.clear("llm:bedrock")
    assert secrets.load("llm:bedrock") is None
