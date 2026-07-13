from __future__ import annotations

import os
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from coeus.core.config import Settings
from coeus.core.errors import AppError
from coeus.services.ai_models import AiModelService
from coeus.services.audit import AuditLog
from coeus.services.embeddings import (
    EMBEDDING_DIMENSIONS,
    EmbeddingService,
    EmbeddingUnavailable,
    GeminiApiEmbeddingProvider,
    LocalFastEmbedProvider,
    MockEmbeddingProvider,
    _coerce_vector,
    _offline_hf_call,
    build_embedding_service,
    cosine_similarity,
    vector_to_pg,
)
from coeus.services.provider_admission import ProviderAdmissionController
from store_projection_helpers import seed_product


def test_mock_embeddings_are_deterministic_384_dimensions() -> None:
    provider = MockEmbeddingProvider()
    vector = provider.embed("boat traffic near St Petersburg")

    assert len(vector) == EMBEDDING_DIMENSIONS
    assert vector == provider.embed("boat traffic near St Petersburg")


def test_mock_embeddings_reward_shared_tokens_not_synonyms() -> None:
    # The mock has no synonym knowledge: cosine tracks shared tokens only. This
    # guards against re-introducing a curated alias map that games acceptance.
    provider = MockEmbeddingProvider()
    anchor = provider.embed("vessel movements Gulf of Finland")
    shares_tokens = provider.embed("vessel movements Baltic approaches")
    disjoint = provider.embed("crop harvest yield forecast")
    synonym_only = provider.embed("boat traffic near St Petersburg")

    assert cosine_similarity(anchor, shares_tokens) > cosine_similarity(anchor, disjoint)
    assert cosine_similarity(anchor, disjoint) == 0.0
    # No shared tokens means no similarity, however close the meaning is.
    assert cosine_similarity(anchor, synonym_only) == 0.0


def test_mock_embedding_of_tokenless_text_is_zero_vector() -> None:
    provider = MockEmbeddingProvider()

    vector = provider.embed("a 1 !")

    assert vector == tuple([0.0] * EMBEDDING_DIMENSIONS)


def test_embedding_provider_setting_is_authoritative_when_key_exists() -> None:
    service = build_embedding_service(
        Settings(environment="test", gemini_api_key="env-secret"),
        AiModelService(Settings(environment="test"), AuditLog()),
    )

    assert service.provider_name == "mock"


def test_build_embedding_service_selects_non_default_providers() -> None:
    audit = AuditLog()

    local = build_embedding_service(
        Settings(environment="test", embedding_provider="local"),
        AiModelService(Settings(environment="test"), audit),
    )
    gemini = build_embedding_service(
        Settings(environment="test", embedding_provider="gemini_api"),
        AiModelService(Settings(environment="test"), audit),
    )

    assert local.provider_name == "local"
    assert gemini.provider_name == "gemini_api"


def test_provider_failure_degrades_to_none() -> None:
    class FailingProvider:
        name = "local"

        def embed(self, _text: str) -> tuple[float, ...]:
            raise EmbeddingUnavailable("model missing")

    service = EmbeddingService(FailingProvider())

    assert service.embed("query", purpose="test") is None


def test_cached_embedding_normalises_and_single_flights_concurrent_misses() -> None:
    class CountingProvider:
        name = "counting"

        def __init__(self) -> None:
            self.calls = 0

        def embed(self, _text: str) -> tuple[float, ...]:
            self.calls += 1
            return (1.0,)

    provider = CountingProvider()
    service = EmbeddingService(provider)
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = tuple(
            pool.map(
                lambda text: service.embed_cached(text, purpose="test"),
                ["  SAME query ", "same   QUERY"] * 20,
            )
        )

    assert results == ((1.0,),) * 40
    assert provider.calls == 1


def test_remote_embedding_reserves_and_commits_shared_provider_capacity() -> None:
    class CountingProvider:
        name = "remote"

        def __init__(self) -> None:
            self.calls = 0

        def embed(self, _text: str) -> tuple[float, ...]:
            self.calls += 1
            return (1.0,)

    provider = CountingProvider()
    admission = ProviderAdmissionController(
        max_concurrent=1,
        max_calls_per_window=2,
        max_calls_per_principal=1,
        window_seconds=60,
    )
    service = EmbeddingService(provider, admission)
    principal = uuid4()

    assert service.embed("first", purpose="test", principal_id=principal) == (1.0,)
    with pytest.raises(AppError, match="Provider capacity"):
        service.embed("second", purpose="test", principal_id=principal)
    assert provider.calls == 1


def test_admitted_embedding_fails_closed_without_principal_context() -> None:
    class Provider:
        name = "remote"

        def embed(self, _text: str) -> tuple[float, ...]:
            raise AssertionError("provider must not be called")

    admission = ProviderAdmissionController(
        max_concurrent=1,
        max_calls_per_window=1,
        max_calls_per_principal=1,
        window_seconds=60,
    )

    assert EmbeddingService(Provider(), admission).embed("query", purpose="test") is None


def test_gemini_provider_requires_runtime_key() -> None:
    provider = GeminiApiEmbeddingProvider(
        Settings(environment="test", embedding_provider="gemini_api"),
        AiModelService(Settings(environment="test"), AuditLog()),
    )

    with pytest.raises(EmbeddingUnavailable):
        provider.embed("query")


def test_mock_embedding_changes_when_product_semantic_text_changes() -> None:
    provider = MockEmbeddingProvider()
    product = seed_product()
    updated = replace(
        product,
        metadata=replace(product.metadata, description="vessel movements in the Gulf of Finland"),
    )

    assert provider.embed(product.metadata.description) != provider.embed(
        updated.metadata.description
    )


def test_local_provider_coerces_short_vectors_without_network() -> None:
    class FakeModel:
        def embed(self, _texts: list[str]) -> list[list[float]]:
            return [[3.0, 4.0]]

    provider = LocalFastEmbedProvider(".local-data/test-models")
    provider._model = FakeModel()

    vector = provider.embed("query")

    assert len(vector) == EMBEDDING_DIMENSIONS
    assert vector[:3] == (0.6, 0.8, 0.0)


def test_gemini_provider_embeds_with_runtime_key(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {"embedding": {"values": [1.0] * EMBEDDING_DIMENSIONS}}

    class FakeClient:
        def __init__(self, *, timeout: int) -> None:
            self.timeout = timeout

        def __enter__(self) -> FakeClient:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def post(
            self,
            url: str,
            *,
            headers: dict[str, str],
            json: dict[str, object],
        ) -> FakeResponse:
            assert "gemini-embedding-001" in url
            assert headers["x-goog-api-key"] == "runtime-secret"
            assert json["outputDimensionality"] == EMBEDDING_DIMENSIONS
            return FakeResponse()

    ai_models = AiModelService(Settings(environment="test"), AuditLog())
    ai_models.configure_api_key("admin", "admin@example.test", "runtime-secret")
    monkeypatch.setattr("coeus.services.embeddings.httpx.Client", FakeClient)

    vector = GeminiApiEmbeddingProvider(Settings(environment="test"), ai_models).embed("query")

    assert len(vector) == EMBEDDING_DIMENSIONS
    assert round(sum(value * value for value in vector), 6) == 1.0


def test_gemini_provider_rejects_invalid_response(monkeypatch: pytest.MonkeyPatch) -> None:
    class BadResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {}

    class FakeClient:
        def __init__(self, *, timeout: int) -> None:
            self.timeout = timeout

        def __enter__(self) -> FakeClient:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def post(self, *_args: object, **_kwargs: object) -> BadResponse:
            return BadResponse()

    ai_models = AiModelService(Settings(environment="test"), AuditLog())
    ai_models.configure_api_key("admin", "admin@example.test", "runtime-secret")
    monkeypatch.setattr("coeus.services.embeddings.httpx.Client", FakeClient)

    with pytest.raises(EmbeddingUnavailable):
        GeminiApiEmbeddingProvider(Settings(environment="test"), ai_models).embed("query")


def test_vector_serialisation_and_empty_similarity() -> None:
    assert vector_to_pg((1.0, -0.5)) == "[1.00000000,-0.50000000]"
    assert vector_to_pg(None) is None
    assert cosine_similarity((), (1.0,)) == 0.0


def test_local_model_loader_uses_offline_mode_and_rejects_non_vectors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class FakeTextEmbedding:
        def __init__(self, **_kwargs: object) -> None:
            return None

        def embed(self, _texts: list[str]) -> list[list[float]]:
            return [[1.0]]

    monkeypatch.setitem(sys.modules, "fastembed", SimpleNamespace(TextEmbedding=FakeTextEmbedding))
    provider = LocalFastEmbedProvider(str(tmp_path / "model"))

    assert provider._load_model() is provider._model
    with pytest.raises(EmbeddingUnavailable, match="not iterable"):
        _coerce_vector(1)


def test_offline_model_boundary_restores_absent_and_existing_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("HF_HUB_OFFLINE", raising=False)
    assert _offline_hf_call(lambda: "loaded") == "loaded"
    assert "HF_HUB_OFFLINE" not in os.environ

    monkeypatch.setenv("HF_HUB_OFFLINE", "custom")
    assert _offline_hf_call(lambda: "loaded") == "loaded"
    assert os.environ["HF_HUB_OFFLINE"] == "custom"
