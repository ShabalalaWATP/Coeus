"""Infrastructure-neutral retrieval embedding port."""

from typing import Protocol


class EmbeddingPort(Protocol):
    @property
    def provider_name(self) -> str: ...

    def embed(self, text: str, *, purpose: str) -> tuple[float, ...] | None: ...

    def embed_cached(self, text: str, *, purpose: str) -> tuple[float, ...] | None: ...
