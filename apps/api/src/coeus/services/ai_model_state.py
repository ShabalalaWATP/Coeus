from dataclasses import dataclass
from datetime import datetime

from coeus.core.config import LlmProviderName
from coeus.core.model_ids import clean_model_ids
from coeus.services.ai_provider_catalog import CURATED_PROVIDER_NAMES, ProviderSpec


@dataclass(frozen=True)
class PersistedAiModelState:
    active_models: dict[LlmProviderName, str]
    custom_models: dict[str, list[str]]
    discovered_models: dict[str, list[str]]
    changed_by: str | None
    changed_at: datetime | None


def restore_model_state(
    payload: dict[str, object], specs: tuple[ProviderSpec, ...]
) -> PersistedAiModelState:
    """Decode and sanitise non-secret AI model configuration."""
    spec_by_name: dict[str, ProviderSpec] = {str(spec.name): spec for spec in specs}
    active_models: dict[LlmProviderName, str] = {spec.name: spec.default_model for spec in specs}
    custom_models: dict[str, list[str]] = {str(spec.name): [] for spec in specs}
    discovered_models: dict[str, list[str]] = {str(spec.name): [] for spec in specs}

    stored_custom = payload.get("custom_models")
    # Migrate the original combined extras list as custom entries. A later
    # provider refresh must never erase these legacy entries.
    if not isinstance(stored_custom, dict):
        stored_custom = payload.get("extra_models")
    _restore_catalogue(stored_custom, custom_models, spec_by_name)
    _restore_catalogue(payload.get("discovered_models"), discovered_models, spec_by_name)
    # Curated providers prune legacy additions so deprecated models cannot
    # survive a catalogue update through persisted state.
    for provider in CURATED_PROVIDER_NAMES:
        custom_models[provider] = []
        discovered_models[provider] = []

    stored_active = payload.get("active_models")
    if isinstance(stored_active, dict):
        for name, model in stored_active.items():
            spec = spec_by_name.get(str(name))
            if spec and isinstance(model, str):
                available = {*spec.models, *custom_models[spec.name], *discovered_models[spec.name]}
                if model in available:
                    active_models[spec.name] = model
    else:
        legacy_model = payload.get("active_model")
        gemini = spec_by_name.get("gemini_api")
        if gemini and isinstance(legacy_model, str) and legacy_model in gemini.models:
            active_models[gemini.name] = legacy_model

    changed_by = payload.get("changed_by")
    return PersistedAiModelState(
        active_models=active_models,
        custom_models=custom_models,
        discovered_models=discovered_models,
        changed_by=changed_by if isinstance(changed_by, str) and changed_by else None,
        changed_at=_parse_datetime(payload.get("changed_at")),
    )


def model_state_payload(
    *,
    active_provider: LlmProviderName,
    active_models: dict[LlmProviderName, str],
    custom_models: dict[str, list[str]],
    discovered_models: dict[str, list[str]],
    changed_by: str | None,
    changed_at: datetime | None,
) -> dict[str, object]:
    return {
        "active_model": active_models[active_provider],
        "active_models": dict(active_models),
        "custom_models": {name: list(models) for name, models in custom_models.items()},
        "discovered_models": {name: list(models) for name, models in discovered_models.items()},
        "changed_by": changed_by,
        "changed_at": changed_at.isoformat() if changed_at else None,
    }


def _restore_catalogue(
    stored: object,
    target: dict[str, list[str]],
    specs: dict[str, ProviderSpec],
) -> None:
    if not isinstance(stored, dict):
        return
    for name, models in stored.items():
        provider = str(name)
        if provider in specs and isinstance(models, list):
            target[provider] = clean_model_ids(models)


def _parse_datetime(value: object) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None
