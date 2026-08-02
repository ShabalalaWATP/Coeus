"""Validation shared by retrieval configuration and connection testing."""

from typing import Literal

from coeus.core.errors import AppError

SearchProvider = Literal["mock", "gemini_api"]
PROVIDER_MODELS: dict[SearchProvider, tuple[str, ...]] = {
    "mock": ("token-hash-v2",),
    "gemini_api": ("gemini-embedding-2", "gemini-embedding-001"),
}


def validate_search_selection(
    provider: str,
    model: str,
    *,
    api_key_configured: bool,
    confirm_external_egress: bool,
) -> SearchProvider:
    """Validate a draft without changing the active retrieval configuration."""
    if provider not in PROVIDER_MODELS:
        raise AppError(422, "provider_not_available", "Search provider is not available.")
    typed_provider = provider
    if model not in PROVIDER_MODELS[typed_provider]:
        raise AppError(422, "model_not_available", "Search model is not available.")
    if typed_provider == "gemini_api":
        if not api_key_configured:
            raise AppError(422, "provider_not_configured", "Save a search API key first.")
        if not confirm_external_egress:
            raise AppError(
                422,
                "external_egress_not_confirmed",
                "Confirm that synthetic search text may be sent to Gemini.",
            )
    return typed_provider
