"""Persistence helpers for administrator-managed LLM credentials."""

from coeus.core.config import LlmProviderName
from coeus.services.ai_provider_catalog import ProviderSpec
from coeus.services.integration_secrets import EncryptedIntegrationSecretStore


def restore_persisted_api_keys(
    specs: tuple[ProviderSpec, ...],
    secret_store: EncryptedIntegrationSecretStore,
    api_keys: dict[LlmProviderName, str | None],
    environment_providers: set[LlmProviderName],
) -> set[LlmProviderName]:
    restored: set[LlmProviderName] = set()
    for spec in specs:
        if spec.name == "mock":
            continue
        persisted = secret_store.load(_secret_name(spec.name))
        if persisted and spec.name not in environment_providers:
            api_keys[spec.name] = persisted
            restored.add(spec.name)
    return restored


def sync_persisted_api_keys(
    specs: tuple[ProviderSpec, ...],
    secret_store: EncryptedIntegrationSecretStore,
    api_keys: dict[LlmProviderName, str | None],
    persisted_providers: set[LlmProviderName],
) -> None:
    for spec in specs:
        if spec.name == "mock":
            continue
        key = api_keys.get(spec.name)
        if spec.name in persisted_providers and key:
            secret_store.save(_secret_name(spec.name), key)
        else:
            secret_store.clear(_secret_name(spec.name))


def set_persisted_api_key(
    api_keys: dict[LlmProviderName, str | None],
    persisted_providers: set[LlmProviderName],
    provider: LlmProviderName,
    api_key: str,
) -> None:
    api_keys[provider] = api_key
    persisted_providers.add(provider)


def _secret_name(provider: LlmProviderName) -> str:
    return f"llm:{provider}"
