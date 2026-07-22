"""Provider-aware model discovery configuration."""

from collections.abc import Sequence
from typing import Protocol

from coeus.core.config import Settings


class ModelDiscovery(Protocol):
    def __call__(
        self,
        provider: str,
        api_key: str,
        timeout: int,
        litellm_base_url: str = "",
        litellm_hosted: bool = False,
    ) -> Sequence[str]: ...


def discover_for_provider(
    settings: Settings,
    discovery: ModelDiscovery,
    provider: str,
    api_key: str,
) -> Sequence[str]:
    return discovery(
        provider,
        api_key,
        settings.llm_api_timeout_seconds,
        settings.litellm_base_url,
        settings.environment in {"dev", "staging", "prod"},
    )
