"""State value objects used by the AI model administration service."""

from dataclasses import dataclass
from datetime import datetime

from coeus.core.config import LlmProviderName


@dataclass(frozen=True)
class AiProviderState:
    name: str
    label: str
    models: tuple[str, ...]
    active_model: str
    api_key_configured: bool
    supports_model_refresh: bool


@dataclass(frozen=True)
class AiModelState:
    provider: str
    active_model: str
    available_models: tuple[str, ...]
    api_key_configured: bool
    embedding_provider: str
    embedded_product_count: int
    changed_by: str | None
    changed_at: datetime | None
    providers: tuple[AiProviderState, ...]


@dataclass(frozen=True)
class AiModelSnapshot:
    provider: LlmProviderName
    active_models: dict[LlmProviderName, str]
    custom_models: dict[str, list[str]]
    discovered_models: dict[str, list[str]]
    api_keys: dict[LlmProviderName, str | None]
    persisted_api_key_providers: set[LlmProviderName]
    changed_by: str | None
    changed_at: datetime | None
