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


def test_unevaluated_provider_cannot_report_complete_search_coverage() -> None:
    index = CapturingIndex()
    state = SimpleNamespace(
        chunk_count=1,
        failed_asset_count=0,
        corpus_version="corpus-v1",
        degraded_reason=None,
        index_status="ready",
        space_id="gemini_api:gemini-embedding-2:1536:g1",
        definitive_no_match_enabled=False,
    )
    service = GroundedSearchService(
        cast(Any, index),
        cast(Any, SimpleNamespace(state=lambda: state)),
        cast(Any, FixedEmbeddings()),
        cast(Any, SimpleNamespace(repository=SimpleNamespace(list_products=lambda: ()))),
        cast(Any, SimpleNamespace(active_acg_ids_for_user=lambda _user_id: frozenset())),
    )

    result = service.search(_actor(), IntakeDetails(title="Synthetic search"), uuid4())

    assert result.coverage_status == "partial"
    assert result.degraded_reason == "provider_evaluation_required"


def test_ready_empty_index_can_report_complete_metadata_coverage() -> None:
    service, _index = _service(
        SimpleNamespace(
            chunk_count=0,
            failed_asset_count=0,
            corpus_version="corpus-v1",
            degraded_reason=None,
            index_status="ready",
            space_id="mock:token-hash-v2:1536:g1",
            definitive_no_match_enabled=True,
        )
    )

    result = service.search(_actor(), IntakeDetails(title="Synthetic search"), uuid4())

    assert result.retrieval_mode == "metadata_only"
    assert result.coverage_status == "complete"
    assert result.degraded_reason is None


def test_unavailable_semantic_index_falls_back_to_lexical_search() -> None:
    service, index = _service(
        SimpleNamespace(
            chunk_count=1,
            failed_asset_count=0,
            corpus_version="corpus-v1",
            degraded_reason="provider_unavailable",
            index_status="failed",
            space_id="mock:token-hash-v2:1536:g1",
            definitive_no_match_enabled=True,
        )
    )

    result = service.search(_actor(), IntakeDetails(title="Synthetic search"), uuid4())

    assert index.query_vector is None
    assert result.retrieval_mode == "lexical_only"
    assert result.coverage_status == "partial"


def test_ready_hybrid_index_reports_complete_coverage() -> None:
    service, _index = _service(
        SimpleNamespace(
            chunk_count=1,
            failed_asset_count=0,
            corpus_version="corpus-v1",
            degraded_reason=None,
            index_status="ready",
            space_id="mock:token-hash-v2:1536:g1",
            definitive_no_match_enabled=True,
        )
    )

    result = service.search(_actor(), IntakeDetails(title="Synthetic search"), uuid4())

    assert result.retrieval_mode == "hybrid"
    assert result.coverage_status == "complete"
    assert result.degraded_reason is None


def _service(state: SimpleNamespace) -> tuple[GroundedSearchService, CapturingIndex]:
    index = CapturingIndex()
    return (
        GroundedSearchService(
            cast(Any, index),
            cast(Any, SimpleNamespace(state=lambda: state)),
            cast(Any, FixedEmbeddings()),
            cast(Any, SimpleNamespace(repository=SimpleNamespace(list_products=lambda: ()))),
            cast(Any, SimpleNamespace(active_acg_ids_for_user=lambda _user_id: frozenset())),
        ),
        index,
    )


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
