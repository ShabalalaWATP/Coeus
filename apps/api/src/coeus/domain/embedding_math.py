"""Pure deterministic embedding and vector operations."""

from hashlib import blake2b
from math import sqrt
from re import findall

EMBEDDING_DIMENSIONS = 384


def mock_embedding(text: str) -> tuple[float, ...]:
    values = [0.0] * EMBEDDING_DIMENSIONS
    for token in canonical_tokens(text):
        digest = blake2b(token.encode("utf-8"), digest_size=8).digest()
        index = int.from_bytes(digest[:4], "big") % EMBEDDING_DIMENSIONS
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        values[index] += sign
    return normalise_vector(values)


def vector_to_pg(vector: tuple[float, ...] | None) -> str | None:
    if vector is None:
        return None
    return "[" + ",".join(f"{value:.8f}" for value in vector[:EMBEDDING_DIMENSIONS]) + "]"


def cosine_similarity(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    if not left or not right:
        return 0.0
    length = min(len(left), len(right), EMBEDDING_DIMENSIONS)
    return max(0.0, min(1.0, sum(left[index] * right[index] for index in range(length))))


def canonical_tokens(text: str) -> tuple[str, ...]:
    tokens = [token for token in findall(r"[a-z0-9]+", text.casefold()) if len(token) >= 2]
    return tuple(dict.fromkeys(tokens))


def normalise_vector(values: list[float]) -> tuple[float, ...]:
    length = sqrt(sum(value * value for value in values))
    if length == 0:
        return tuple(0.0 for _ in range(EMBEDDING_DIMENSIONS))
    return tuple(round(value / length, 8) for value in values[:EMBEDDING_DIMENSIONS])
