from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

from coeus.domain.auth import RoleName, UserAccount
from coeus.domain.search_index import GroundedProductEvidence
from coeus.domain.tickets import IntakeDetails
from coeus.services.grounded_search import GroundedSearchService


class CapturingIndex:
    def __init__(self) -> None:
        self.query_vector: tuple[float, ...] | None = None

    def search(
        self,
        _scope: object,
        _query: str,
        query_vector: tuple[float, ...] | None,
        _allowed_product_ids: frozenset[object],
    ) -> tuple[GroundedProductEvidence, ...]:
        self.query_vector = query_vector
        return (
            GroundedProductEvidence(
                product_id=uuid4(),
                passages=(),
                lexical_rank=2,
                vector_rank=1,
                lexical_score=0.2,
                vector_score=0.8,
            ),
        )


class FixedEmbeddings:
    def embed(self, *_args: object, **_kwargs: object) -> tuple[float, ...]:
        return (0.25,) * 1536


def test_corpus_stale_generation_still_contributes_semantic_results() -> None:
    index = CapturingIndex()
    state = SimpleNamespace(
        chunk_count=1,
        degraded_reason="corpus_changed",
        index_status="stale",
        space_id="mock:token-hash-v2:1536:g1",
    )
    service = GroundedSearchService(
        cast(Any, index),
        cast(Any, SimpleNamespace(state=lambda: state)),
        cast(Any, FixedEmbeddings()),
        cast(Any, SimpleNamespace(repository=SimpleNamespace(list_products=lambda: ()))),
        cast(Any, SimpleNamespace(active_acg_ids_for_user=lambda _user_id: frozenset())),
    )

    result = service.search(_actor(), IntakeDetails(title="Synthetic search"), uuid4())

    assert index.query_vector == (0.25,) * 1536
    assert result.retrieval_mode == "hybrid"
    assert result.degraded_reason == "corpus_changed"
    assert result.profile_space_id == "mock:token-hash-v2:1536:g1"


def _actor() -> UserAccount:
    return UserAccount(
        user_id=uuid4(),
        username="searcher@example.test",
        display_name="Synthetic searcher",
        roles=frozenset({RoleName.USER}),
        permissions=frozenset(),
        password_hash="synthetic-hash",  # noqa: S106
        is_active=True,
        clearance_level=3,
    )
