from math import isclose
from typing import Any, ClassVar

import pytest

from coeus.core.config import Settings
from coeus.persistence.state_store import MemoryStateStore
from coeus.services.audit import AuditLog
from coeus.services.integration_secrets import EncryptedIntegrationSecretStore
from coeus.services.search_configuration import (
    SEARCH_EMBEDDING_DIMENSIONS,
    SearchConfigurationService,
)
from coeus.services.search_embeddings import (
    SearchEmbeddingService,
    SearchEmbeddingUnavailable,
    _strict_vector,
)


def _configured(provider: str = "mock") -> SearchConfigurationService:
    settings = Settings(environment="test")
    state = MemoryStateStore()
    service = SearchConfigurationService(
        settings,
        AuditLog(),
        state,
        EncryptedIntegrationSecretStore(state, settings),
    )
    if provider == "gemini_api":
        service.configure_key("1", "admin", "search-secret-value")
        service.configure("1", "admin", provider, "gemini-embedding-2", True)
    return service


def test_mock_search_embedding_is_deterministic_and_strict() -> None:
    configuration = _configured()
    embeddings = SearchEmbeddingService(Settings(environment="test"), configuration)
    left = embeddings.embed("Russian armour", purpose="query", principal_id=None)
    right = embeddings.embed("Russian armour", purpose="query", principal_id=None)

    assert left == right
    assert left is not None
    assert len(left) == SEARCH_EMBEDDING_DIMENSIONS
    assert isclose(sum(value * value for value in left), 1.0, abs_tol=1e-6)
    assert embeddings.embed_many(("one", "two"), principal_id=_uuid()) is not None
    with pytest.raises(ValueError, match="limited to 100"):
        embeddings.embed_many(tuple(str(i) for i in range(101)), principal_id=_uuid())


def test_gemini_search_embedding_uses_retrieval_prefix_and_1536_dimensions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configuration = _configured("gemini_api")
    client = _FakeClient()
    monkeypatch.setattr("coeus.services.search_embeddings.httpx.Client", lambda **_kwargs: client)
    embeddings = SearchEmbeddingService(Settings(environment="test"), configuration)

    vector = embeddings.embed("Donbas movements", purpose="query", principal_id=_uuid())

    assert vector is not None and len(vector) == SEARCH_EMBEDDING_DIMENSIONS
    assert "gemini-embedding-2" in str(client.captured["url"])
    body = client.captured["json"]
    assert body["outputDimensionality"] == SEARCH_EMBEDDING_DIMENSIONS
    assert body["content"]["parts"][0]["text"].startswith("task: search result | query:")
    assert client.captured["headers"]["x-goog-api-key"] == "search-secret-value"


def test_invalid_provider_vector_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    configuration = _configured("gemini_api")
    monkeypatch.setattr(
        "coeus.services.search_embeddings.httpx.Client",
        lambda **_kwargs: _FakeClient(values=[1.0] * 12),
    )
    embeddings = SearchEmbeddingService(Settings(environment="test"), configuration)
    assert embeddings.embed("query", purpose="query", principal_id=_uuid()) is None


def test_search_embedding_cache_is_bounded_and_tokenless_input_is_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("coeus.services.search_embeddings.SEARCH_EMBEDDING_CACHE_LIMIT", 1)
    embeddings = SearchEmbeddingService(Settings(environment="test"), _configured())

    assert embeddings.embed("a 1 !", purpose="query", principal_id=None) == (0.0,) * 1536
    embeddings.embed("first", purpose="query", principal_id=None)
    embeddings.embed("second", purpose="query", principal_id=None)

    assert len(embeddings._cache) == 1


def test_gemini_batch_embeddings_support_admission_and_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configuration = _configured("gemini_api")
    admission = _Admission()
    client = _BatchClient(2)
    monkeypatch.setattr("coeus.services.search_embeddings.httpx.Client", lambda **_kwargs: client)
    plain = SearchEmbeddingService(Settings(environment="test"), configuration)
    assert len(plain.embed_many(("one", "two"), principal_id=_uuid()) or ()) == 2
    embeddings = SearchEmbeddingService(Settings(environment="test"), configuration, admission)

    vectors = embeddings.embed_many(("one", "two"), principal_id=_uuid())

    assert vectors is not None and len(vectors) == 2
    assert admission.reservation.committed is True
    assert client.captured["json"]["requests"][0]["content"]["parts"][0]["text"] == ("text: one")
    assert embeddings.embed_many((), principal_id=_uuid()) == ()

    monkeypatch.setattr(
        "coeus.services.search_embeddings.httpx.Client",
        lambda **_kwargs: _BatchClient(1),
    )
    assert embeddings.embed_many(("one", "two"), principal_id=_uuid()) is None


def test_gemini_requires_principal_and_key_and_rejects_non_finite_values() -> None:
    configuration = _configured("gemini_api")
    embeddings = SearchEmbeddingService(Settings(environment="test"), configuration)
    assert embeddings.embed("query", purpose="query", principal_id=None) is None

    configuration._persisted_key = None
    assert embeddings.embed("different", purpose="document", principal_id=_uuid()) is None

    with pytest.raises(SearchEmbeddingUnavailable, match="invalid_values"):
        _strict_vector([float("nan")] * SEARCH_EMBEDDING_DIMENSIONS)


class _FakeClient:
    captured: ClassVar[dict[str, Any]] = {}

    def __init__(self, values: list[float] | None = None) -> None:
        self._values = values or [1.0] * SEARCH_EMBEDDING_DIMENSIONS

    def __enter__(self) -> "_FakeClient":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def post(self, url: str, **kwargs: Any) -> "_FakeClient":
        self.captured.update(url=url, **kwargs)
        return self

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        return {"embedding": {"values": self._values}}


class _BatchClient(_FakeClient):
    def __init__(self, count: int) -> None:
        super().__init__()
        self._count = count

    def json(self) -> dict[str, object]:
        return {"embeddings": [{"values": self._values} for _ in range(self._count)]}


class _Reservation:
    committed = False

    def __enter__(self):
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def commit(self) -> None:
        self.committed = True


class _Admission:
    def __init__(self) -> None:
        self.reservation = _Reservation()

    def reserve(self, _principal_id: object) -> _Reservation:
        return self.reservation


def _uuid():
    from uuid import uuid4

    return uuid4()
