"""Static catalogue of the selectable LLM providers.

Gemini API is the primary provider and always listed first; the others are
opt-in alternatives. Model lists and defaults come from settings so a
deployment can pin its own allow-list per provider.
"""

from dataclasses import dataclass

from coeus.core.config import LlmProviderName, Settings


@dataclass(frozen=True)
class ProviderSpec:
    name: LlmProviderName
    label: str
    models: tuple[str, ...]
    default_model: str


def provider_specs(settings: Settings) -> tuple[ProviderSpec, ...]:
    """All selectable providers, primary first, offline fallback last."""
    return (
        _spec(
            "gemini_api",
            "Gemini API (primary)",
            settings.available_gemini_models,
            settings.gemini_api_model,
        ),
        _spec(
            "openai_api", "OpenAI API", settings.available_openai_models, settings.openai_api_model
        ),
        _spec(
            "vertex_ai",
            "GCP Vertex AI",
            settings.available_vertex_models,
            settings.vertex_api_model,
        ),
        _spec(
            "bedrock", "AWS Bedrock", settings.available_bedrock_models, settings.bedrock_api_model
        ),
        ProviderSpec(name="mock", label="Mock (offline)", models=("mock",), default_model="mock"),
    )


def spec_for(settings: Settings, name: str) -> ProviderSpec | None:
    return next((spec for spec in provider_specs(settings) if spec.name == name), None)


def initial_api_keys(settings: Settings) -> dict[str, str | None]:
    """Environment-supplied keys per provider; mock never needs one."""
    return {
        "gemini_api": settings.gemini_api_key,
        "openai_api": settings.openai_api_key,
        "vertex_ai": settings.vertex_api_key,
        "bedrock": settings.bedrock_api_key,
        "mock": None,
    }


def _spec(name: LlmProviderName, label: str, models: list[str], default_model: str) -> ProviderSpec:
    catalogue = tuple(models)
    default = default_model if default_model in catalogue else catalogue[0]
    return ProviderSpec(name=name, label=label, models=catalogue, default_model=default)
