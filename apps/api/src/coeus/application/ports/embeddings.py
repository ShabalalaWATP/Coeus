"""Infrastructure-neutral retrieval embedding port."""

from typing import Protocol
from uuid import UUID

EMBEDDING_WORKLOAD_PRINCIPAL = UUID("00000000-0000-0000-0000-000000000001")


class EmbeddingPort(Protocol):
    @property
    def provider_name(self) -> str:
        pass

    @property
    def model_name(self) -> str:
        pass

    @property
    def space_id(self) -> str:
        pass

    def embed(
        self, text: str, *, purpose: str, principal_id: UUID | None = None
    ) -> tuple[float, ...] | None:
        pass

    def embed_cached(
        self, text: str, *, purpose: str, principal_id: UUID | None = None
    ) -> tuple[float, ...] | None:
        pass
