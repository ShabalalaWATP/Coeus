"""Strict 1,536-dimension embeddings for the generation-aware search index."""

from collections import OrderedDict
from hashlib import blake2b
from math import isfinite, sqrt
from re import findall
from threading import RLock
from typing import Literal
from uuid import UUID

import httpx

from coeus.application.ports.admission import ProviderAdmission
from coeus.core.config import Settings
from coeus.core.logging import get_logger
from coeus.domain.search_index import SEARCH_EMBEDDING_DIMENSIONS
from coeus.services.search_configuration import SearchConfigurationService

SearchEmbeddingPurpose = Literal["query", "document", "test"]
SEARCH_EMBEDDING_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:embedContent"
)
SEARCH_BATCH_EMBEDDING_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:batchEmbedContents"
)
SEARCH_EMBEDDING_CACHE_LIMIT = 2_048
logger = get_logger(__name__)


class SearchEmbeddingUnavailable(RuntimeError):
    """Raised when a v2 search vector cannot be produced safely."""


class SearchEmbeddingService:
    def __init__(
        self,
        settings: Settings,
        configuration: SearchConfigurationService,
        admission: ProviderAdmission | None = None,
    ) -> None:
        self._settings = settings
        self._configuration = configuration
        self._admission = admission
        self._cache: OrderedDict[str, tuple[float, ...]] = OrderedDict()
        self._lock = RLock()

    @property
    def space_id(self) -> str:
        return self._configuration.state().space_id

    def embed(
        self,
        text: str,
        *,
        purpose: SearchEmbeddingPurpose,
        principal_id: UUID | None,
    ) -> tuple[float, ...] | None:
        bounded = " ".join(text.split())[:32_000]
        digest = blake2b(bounded.casefold().encode(), digest_size=16).hexdigest()
        cache_key = f"{self.space_id}:{purpose}:{digest}"
        with self._lock:
            cached = self._cache.get(cache_key)
            if cached is not None:
                self._cache.move_to_end(cache_key)
                return cached
        try:
            vector = self._embed_uncached(bounded, purpose, principal_id)
        except SearchEmbeddingUnavailable as exc:
            logger.warning(
                "search_embedding_unavailable",
                extra={"provider": self._configuration.state().provider, "reason": str(exc)},
            )
            return None
        with self._lock:
            self._cache[cache_key] = vector
            if len(self._cache) > SEARCH_EMBEDDING_CACHE_LIMIT:
                self._cache.popitem(last=False)
        return vector

    def _embed_uncached(
        self,
        text: str,
        purpose: SearchEmbeddingPurpose,
        principal_id: UUID | None,
    ) -> tuple[float, ...]:
        state = self._configuration.state()
        if state.provider == "mock":
            return _mock_embedding(text)
        if principal_id is None:
            raise SearchEmbeddingUnavailable("principal_missing")
        if self._admission is None:
            return self._gemini(text, purpose)
        with self._admission.reserve(principal_id) as reservation:
            vector = self._gemini(text, purpose)
            reservation.commit()
            return vector

    def embed_many(
        self,
        texts: tuple[str, ...],
        *,
        principal_id: UUID,
    ) -> tuple[tuple[float, ...], ...] | None:
        if not texts:
            return ()
        if len(texts) > 100:
            raise ValueError("Search embedding batches are limited to 100 texts.")
        state = self._configuration.state()
        if state.provider == "mock":
            return tuple(_mock_embedding(text) for text in texts)
        try:
            if self._admission is None:
                return self._gemini_batch(texts)
            with self._admission.reserve(principal_id) as reservation:
                vectors = self._gemini_batch(texts)
                reservation.commit()
                return vectors
        except SearchEmbeddingUnavailable as exc:
            logger.warning(
                "search_embedding_batch_unavailable",
                extra={"provider": state.provider, "reason": str(exc)},
            )
            return None

    def _gemini(self, text: str, purpose: SearchEmbeddingPurpose) -> tuple[float, ...]:
        state = self._configuration.state()
        api_key = self._configuration.api_key()
        if not api_key:
            raise SearchEmbeddingUnavailable("key_missing")
        prefixed = f"task: search result | query: {text}" if purpose == "query" else f"text: {text}"
        try:
            with httpx.Client(timeout=self._settings.gemini_api_timeout_seconds) as client:
                response = client.post(
                    SEARCH_EMBEDDING_URL.format(model=state.model),
                    headers={"x-goog-api-key": api_key},
                    json={
                        "content": {"parts": [{"text": prefixed}]},
                        "outputDimensionality": SEARCH_EMBEDDING_DIMENSIONS,
                    },
                )
                response.raise_for_status()
                payload = response.json()
        except Exception as exc:  # pragma: no cover - external boundary
            raise SearchEmbeddingUnavailable("provider_failed") from exc
        values = payload.get("embedding", {}).get("values")
        return _strict_vector(values)

    def _gemini_batch(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]:
        state = self._configuration.state()
        api_key = self._configuration.api_key()
        if not api_key:
            raise SearchEmbeddingUnavailable("key_missing")
        requests = [
            {
                "model": f"models/{state.model}",
                "content": {"parts": [{"text": f"text: {' '.join(text.split())[:32000]}"}]},
                "outputDimensionality": SEARCH_EMBEDDING_DIMENSIONS,
            }
            for text in texts
        ]
        try:
            with httpx.Client(timeout=self._settings.gemini_api_timeout_seconds) as client:
                response = client.post(
                    SEARCH_BATCH_EMBEDDING_URL.format(model=state.model),
                    headers={"x-goog-api-key": api_key},
                    json={"requests": requests},
                )
                response.raise_for_status()
                payload = response.json()
        except Exception as exc:  # pragma: no cover - external boundary
            raise SearchEmbeddingUnavailable("provider_failed") from exc
        embeddings = payload.get("embeddings")
        if not isinstance(embeddings, list) or len(embeddings) != len(texts):
            raise SearchEmbeddingUnavailable("invalid_batch")
        return tuple(_strict_vector(item.get("values")) for item in embeddings)


def _strict_vector(values: object) -> tuple[float, ...]:
    if not isinstance(values, list) or len(values) != SEARCH_EMBEDDING_DIMENSIONS:
        raise SearchEmbeddingUnavailable("invalid_dimensions")
    vector = tuple(float(value) for value in values)
    if any(not isfinite(value) for value in vector):
        raise SearchEmbeddingUnavailable("invalid_values")
    return _normalise(vector)


def _mock_embedding(text: str) -> tuple[float, ...]:
    values = [0.0] * SEARCH_EMBEDDING_DIMENSIONS
    for token in dict.fromkeys(findall(r"[a-z0-9]+", text.casefold())):
        if len(token) < 2:
            continue
        digest = blake2b(token.encode(), digest_size=8).digest()
        index = int.from_bytes(digest[:4], "big") % SEARCH_EMBEDDING_DIMENSIONS
        values[index] += 1.0 if digest[4] % 2 == 0 else -1.0
    return _normalise(tuple(values))


def _normalise(values: tuple[float, ...]) -> tuple[float, ...]:
    magnitude = sqrt(sum(value * value for value in values))
    if magnitude == 0:
        return tuple(0.0 for _ in values)
    return tuple(round(value / magnitude, 8) for value in values)
