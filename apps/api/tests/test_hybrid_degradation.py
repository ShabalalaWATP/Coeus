from typing import Any, cast

from sqlalchemy.engine import Connection

from coeus.domain.store import StoreProduct
from coeus.persistence.store_projection_search import hybrid_candidates
from coeus.repositories.store_hybrid import memory_hybrid_candidates
from coeus.services.embeddings import EmbeddingService, MockEmbeddingProvider
from coeus.services.store_semantics import product_semantic_text
from store_projection_helpers import (
    _acg_rows,
    _asset_rows,
    _label_rows,
    _product_row,
    filters,
    seed_product,
    visibility_scope,
)

_DIMENSIONS = 384
_UNIT_VECTOR = (1.0, *([0.0] * (_DIMENSIONS - 1)))


class _Result:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    def mappings(self) -> "_Result":
        return self

    def __iter__(self) -> Any:
        return iter(self._rows)


class _Connection:
    def __init__(self, product_rows: list[dict[str, Any]], product: StoreProduct) -> None:
        self._product_rows = product_rows
        self._product = product

    def execute(self, statement: object, params: dict[str, Any] | None = None) -> _Result:
        sql = str(statement).strip()
        if sql.startswith("WITH scoped AS"):
            return _Result(self._product_rows)
        if "intelligence_store_assets" in sql:
            return _Result(_asset_rows(self._product))
        if "intelligence_store_product_acgs" in sql:
            return _Result(_acg_rows(self._product))
        if "intelligence_store_semantic_labels" in sql:
            return _Result(_label_rows(self._product))
        return _Result([])


def _row(product: StoreProduct, *, vector_rank: int | None) -> dict[str, Any]:
    return _product_row(product) | {
        "lexical_rank": 1,
        "lexical_score": 0.5,
        "vector_rank": vector_rank,
        "vector_score": None if vector_rank is None else 0.8,
    }


def test_projection_flags_lexical_only_when_no_candidate_has_embedding() -> None:
    product = seed_product()
    connection = _Connection([_row(product, vector_rank=None)], product)

    candidates = hybrid_candidates(
        cast(Connection, connection), filters(), visibility_scope(product), "query", "[0.1,0.2]"
    )

    assert candidates
    assert all(candidate.lexical_only for candidate in candidates)


def test_projection_not_lexical_only_when_a_candidate_has_embedding() -> None:
    product = seed_product()
    connection = _Connection([_row(product, vector_rank=1)], product)

    candidates = hybrid_candidates(
        cast(Connection, connection), filters(), visibility_scope(product), "query", "[0.1,0.2]"
    )

    assert candidates
    assert all(not candidate.lexical_only for candidate in candidates)


def test_memory_lexical_only_when_query_not_embedded() -> None:
    product = seed_product()

    candidates = memory_hybrid_candidates((product,), product.metadata.title, None)

    assert candidates
    assert all(candidate.lexical_only for candidate in candidates)


def test_memory_lexical_only_when_query_embeds_but_no_candidate_vector() -> None:
    class NoneService:
        def embed(
            self, _text: str, *, purpose: str, principal_id: object | None = None
        ) -> tuple[float, ...] | None:
            return None

    product = seed_product()

    candidates = memory_hybrid_candidates(
        (product,),
        product.metadata.title,
        _UNIT_VECTOR,
        cast(EmbeddingService, NoneService()),
    )

    assert candidates
    assert all(candidate.lexical_only for candidate in candidates)


def test_memory_uses_supplied_provider_for_product_vectors() -> None:
    calls: list[str] = []

    class StubService:
        def embed(
            self, text: str, *, purpose: str, principal_id: object | None = None
        ) -> tuple[float, ...] | None:
            calls.append(purpose)
            return _UNIT_VECTOR

    product = seed_product()

    candidates = memory_hybrid_candidates(
        (product,), "query", _UNIT_VECTOR, cast(EmbeddingService, StubService())
    )

    assert calls == ["memory-candidate"]
    assert candidates
    assert any(candidate.vector_rank is not None for candidate in candidates)
    assert all(not candidate.lexical_only for candidate in candidates)


def test_memory_default_mock_provider_shares_query_space() -> None:
    product = seed_product()
    query_vector = MockEmbeddingProvider().embed(product_semantic_text(product))

    candidates = memory_hybrid_candidates((product,), "unrelated terms", query_vector)

    assert candidates
    assert any(candidate.vector_rank is not None for candidate in candidates)
    assert all(not candidate.lexical_only for candidate in candidates)
