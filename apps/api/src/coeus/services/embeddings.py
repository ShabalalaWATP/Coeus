from collections.abc import Callable, Iterable
from hashlib import blake2b
from math import sqrt
from os import environ
from pathlib import Path
from re import findall
from typing import TYPE_CHECKING, Protocol

import httpx

from coeus.core.config import Settings
from coeus.core.logging import get_logger

if TYPE_CHECKING:
    from coeus.services.ai_models import AiModelService

EMBEDDING_DIMENSIONS = 384
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


class EmbeddingService:
    """Stable wrapper that degrades provider failures to lexical-only search.

    Retrieval maths uses cosine distance over 384-dimensional, L2-normalised
    vectors. Callers receive `None` when the configured provider cannot produce
    a vector, which means lexical ranking remains the only active retrieval leg.
    """

    def __init__(self, provider: EmbeddingProvider) -> None:
        self._provider = provider
        self._warned: set[str] = set()

    @property
    def provider_name(self) -> str:
        return self._provider.name

    def embed(self, text: str, *, purpose: str) -> tuple[float, ...] | None:
        try:
            return self._provider.embed(text)
        except EmbeddingUnavailable as exc:
            self._warn_once(str(exc), purpose)
            return None

    def _warn_once(self, reason: str, purpose: str) -> None:
        key = f"{self.provider_name}:{reason}"
        if key in self._warned:
            return
        self._warned.add(key)
        logger.warning(
            "embedding_provider_unavailable",
            extra={"provider": self.provider_name, "purpose": purpose, "reason": reason},
        )


class MockEmbeddingProvider:
    """Hash canonical tokens into a deterministic local retrieval vector.

    Each token is lower-cased, lightly canonicalised, hashed with BLAKE2b and
    added to one signed dimension. The final vector is L2-normalised, so cosine
    similarity can be re-derived by hand from shared canonical token buckets.
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
        self._model: object | None = None

    def embed(self, text: str) -> tuple[float, ...]:
        model = self._load_model()
        try:
            vector = next(iter(model.embed([text])))  # type: ignore[attr-defined]
        except Exception as exc:  # pragma: no cover - provider boundary
            raise EmbeddingUnavailable("local model embedding failed") from exc
        return _normalise(_coerce_vector(vector))

    def _load_model(self) -> object:
        if self._model is not None:
            return self._model
        try:
            from fastembed import TextEmbedding
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise EmbeddingUnavailable("fastembed package is not installed") from exc
        self._model_path.mkdir(parents=True, exist_ok=True)
        self._model = _offline_hf_call(
            lambda: TextEmbedding(
                cache_dir=str(self._model_path),
                model_name="BAAI/bge-small-en-v1.5",
            )
        )
        return self._model


class GeminiApiEmbeddingProvider:
    name = "gemini_api"

    def __init__(self, settings: Settings, ai_models: "AiModelService") -> None:
        self._settings = settings
        self._ai_models = ai_models

    def embed(self, text: str) -> tuple[float, ...]:
        api_key = self._ai_models.api_key()
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


def build_embedding_service(settings: Settings, ai_models: "AiModelService") -> EmbeddingService:
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


TOKEN_ALIASES = {
    "boat": "vessel",
    "boats": "vessel",
    "craft": "vessel",
    "gulf": "gulf-finland",
    "finland": "gulf-finland",
    "movement": "movement",
    "movements": "movement",
    "petersburg": "gulf-finland",
    "shipping": "vessel",
    "ships": "vessel",
    "st": "gulf-finland",
    "traffic": "movement",
    "vessels": "vessel",
}


def _canonical_tokens(text: str) -> tuple[str, ...]:
    tokens = []
    for token in findall(r"[a-z0-9]+", text.casefold()):
        if len(token) < 2:
            continue
        tokens.append(TOKEN_ALIASES.get(token, token))
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
