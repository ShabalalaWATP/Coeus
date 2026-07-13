from collections import OrderedDict
from collections.abc import Callable, Iterable
from hashlib import blake2b
from math import sqrt
from os import environ
from pathlib import Path
from re import findall
from threading import Event, RLock
from typing import Protocol, cast

import httpx

from coeus.core.config import Settings
from coeus.core.logging import get_logger

EMBEDDING_DIMENSIONS = 384
EMBEDDING_CACHE_LIMIT = 2048
GEMINI_EMBEDDING_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:embedContent"
)

logger = get_logger(__name__)


class EmbeddingUnavailable(RuntimeError):
    """Raised when a selected provider cannot return a retrieval embedding."""


class EmbeddingProvider(Protocol):
    """Provider contract for deterministic 384-dimension retrieval embeddings."""

    name: str

    def embed(self, text: str) -> tuple[float, ...]:
        """Return a normalised vector for text or raise `EmbeddingUnavailable`."""


class ApiKeyProvider(Protocol):
    def api_key(self, provider: str | None = None) -> str | None:
        pass


class _FastEmbedModel(Protocol):
    def embed(self, texts: list[str]) -> Iterable[object]:
        pass


class EmbeddingService:
    """Stable wrapper that degrades provider failures to lexical-only search.

    Retrieval maths uses cosine distance over 384-dimensional, L2-normalised
    vectors. Callers receive `None` when the configured provider cannot produce
    a vector, which means lexical ranking remains the only active retrieval leg.
    """

    def __init__(self, provider: EmbeddingProvider) -> None:
        self._provider = provider
        self._warned: set[str] = set()
        self._cache: OrderedDict[str, tuple[float, ...] | None] = OrderedDict()
        self._inflight: dict[str, Event] = {}
        self._lock = RLock()

    @property
    def provider_name(self) -> str:
        return self._provider.name

    def embed(self, text: str, *, purpose: str) -> tuple[float, ...] | None:
        try:
            return self._provider.embed(text)
        except EmbeddingUnavailable as exc:
            self._warn_once(str(exc), purpose)
            return None

    def embed_cached(self, text: str, *, purpose: str) -> tuple[float, ...] | None:
        """Embed a normalised key once, coalescing concurrent cache misses."""
        normalised = " ".join(text.split()).casefold()
        digest = blake2b(normalised.encode("utf-8"), digest_size=16).hexdigest()
        key = f"{self.provider_name}:{digest}"
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                return self._cache[key]
            event = self._inflight.get(key)
            leader = event is None
            if event is None:
                event = Event()
                self._inflight[key] = event
        if not leader:
            event.wait()
            with self._lock:
                return self._cache.get(key)
        try:
            vector = self.embed(text, purpose=purpose)
            with self._lock:
                self._cache[key] = vector
                if len(self._cache) > EMBEDDING_CACHE_LIMIT:
                    self._cache.popitem(last=False)
            return vector
        finally:
            with self._lock:
                completed = self._inflight.pop(key)
                completed.set()

    def _warn_once(self, reason: str, purpose: str) -> None:
        key = f"{self.provider_name}:{reason}"
        with self._lock:
            if key in self._warned:
                return
            self._warned.add(key)
        logger.warning(
            "embedding_provider_unavailable",
            extra={"provider": self.provider_name, "purpose": purpose, "reason": reason},
        )


class MockEmbeddingProvider:
    """Hash distinct tokens into a deterministic local retrieval vector.

    Each token is lower-cased, hashed with BLAKE2b and added to one signed
    dimension. The digest is stable across runs and platforms and does not
    depend on ``PYTHONHASHSEED``. The final vector is L2-normalised, so cosine
    similarity is driven purely by shared tokens: it carries no cross-vocabulary
    semantic power and is intended only as a deterministic CI stand-in.
    """

    name = "mock"

    def embed(self, text: str) -> tuple[float, ...]:
        values = [0.0] * EMBEDDING_DIMENSIONS
        for token in _canonical_tokens(text):
            digest = blake2b(token.encode("utf-8"), digest_size=8).digest()
            index = int.from_bytes(digest[:4], "big") % EMBEDDING_DIMENSIONS
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            values[index] += sign
        return _normalise(values)


class LocalFastEmbedProvider:
    name = "local"

    def __init__(self, model_path: str) -> None:
        self._model_path = Path(model_path)
        self._model: _FastEmbedModel | None = None

    def embed(self, text: str) -> tuple[float, ...]:
        model = self._load_model()
        try:
            vector = next(iter(model.embed([text])))
        except Exception as exc:  # pragma: no cover - provider boundary
            raise EmbeddingUnavailable("local model embedding failed") from exc
        return _normalise(_coerce_vector(vector))

    def _load_model(self) -> _FastEmbedModel:
        if self._model is not None:
            return self._model
        try:
            from fastembed import TextEmbedding
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise EmbeddingUnavailable("fastembed package is not installed") from exc
        self._model_path.mkdir(parents=True, exist_ok=True)
        self._model = cast(
            _FastEmbedModel,
            _offline_hf_call(
                lambda: TextEmbedding(
                    cache_dir=str(self._model_path),
                    model_name="BAAI/bge-small-en-v1.5",
                )
            ),
        )
        return self._model


class GeminiApiEmbeddingProvider:
    name = "gemini_api"

    def __init__(self, settings: Settings, ai_models: ApiKeyProvider) -> None:
        self._settings = settings
        self._ai_models = ai_models

    def embed(self, text: str) -> tuple[float, ...]:
        # Embeddings always use the Gemini key, whichever chat provider is
        # active: the embedding provider is a separate configuration switch.
        api_key = self._ai_models.api_key("gemini_api")
        if not api_key:
            raise EmbeddingUnavailable("gemini api key is not configured")
        payload = {
            "content": {"parts": [{"text": text}]},
            "outputDimensionality": EMBEDDING_DIMENSIONS,
        }
        try:
            with httpx.Client(timeout=self._settings.gemini_api_timeout_seconds) as client:
                response = client.post(
                    GEMINI_EMBEDDING_URL.format(model=self._settings.gemini_embedding_model),
                    headers={"x-goog-api-key": api_key},
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
        except Exception as exc:  # pragma: no cover - network boundary
            raise EmbeddingUnavailable("gemini embedding request failed") from exc
        values = data.get("embedding", {}).get("values")
        if not isinstance(values, list):
            raise EmbeddingUnavailable("gemini embedding response was invalid")
        return _normalise(_coerce_vector(values))


def build_embedding_service(settings: Settings, ai_models: ApiKeyProvider) -> EmbeddingService:
    provider: EmbeddingProvider
    if settings.embedding_provider == "local":
        provider = LocalFastEmbedProvider(settings.embedding_model_path)
    elif settings.embedding_provider == "gemini_api":
        provider = GeminiApiEmbeddingProvider(settings, ai_models)
    else:
        provider = MockEmbeddingProvider()
    return EmbeddingService(provider)


def vector_to_pg(vector: tuple[float, ...] | None) -> str | None:
    if vector is None:
        return None
    return "[" + ",".join(f"{value:.8f}" for value in vector[:EMBEDDING_DIMENSIONS]) + "]"


def cosine_similarity(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    if not left or not right:
        return 0.0
    length = min(len(left), len(right), EMBEDDING_DIMENSIONS)
    return max(0.0, min(1.0, sum(left[index] * right[index] for index in range(length))))


def _canonical_tokens(text: str) -> tuple[str, ...]:
    tokens = [token for token in findall(r"[a-z0-9]+", text.casefold()) if len(token) >= 2]
    return tuple(dict.fromkeys(tokens))


def _normalise(values: list[float]) -> tuple[float, ...]:
    length = sqrt(sum(value * value for value in values))
    if length == 0:
        return tuple(0.0 for _ in range(EMBEDDING_DIMENSIONS))
    return tuple(round(value / length, 8) for value in values[:EMBEDDING_DIMENSIONS])


def _coerce_vector(values: object) -> list[float]:
    if not isinstance(values, Iterable):
        raise EmbeddingUnavailable("embedding response was not iterable")
    vector = [float(value) for value in tuple(values)[:EMBEDDING_DIMENSIONS]]
    if len(vector) < EMBEDDING_DIMENSIONS:
        vector.extend(0.0 for _ in range(EMBEDDING_DIMENSIONS - len(vector)))
    return vector


def _offline_hf_call(factory: Callable[[], object]) -> object:
    previous = environ.get("HF_HUB_OFFLINE")
    environ["HF_HUB_OFFLINE"] = "1"
    try:
        return factory()
    except Exception as exc:  # pragma: no cover - optional model boundary
        raise EmbeddingUnavailable("local model is not available in the cache") from exc
    finally:
        if previous is None:
            environ.pop("HF_HUB_OFFLINE", None)
        else:
            environ["HF_HUB_OFFLINE"] = previous
