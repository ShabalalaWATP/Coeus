from dataclasses import replace
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID, uuid4

import pytest

from coeus.domain.search_index import (
    SEARCH_EMBEDDING_DIMENSIONS,
    SearchChunk,
    SearchIndexProfile,
    SearchTicketDocument,
)
from coeus.services import search_indexing
from coeus.services.document_extraction import DocumentExtractionError
from coeus.services.search_indexing import SearchIndexingService
from store_projection_helpers import seed_product


class _Configuration:
    def __init__(
        self,
        *,
        ready_error: bool = False,
        failed_error: bool = False,
        index_status: str = "ready",
    ) -> None:
        self.ready_error = ready_error
        self.failed_error = failed_error
        self.index_status = index_status
        self.failed: list[str] = []

    def state(self) -> SimpleNamespace:
        return SimpleNamespace(index_status=self.index_status)

    def mark_indexing(self, _actor_id: str) -> SimpleNamespace:
        return SimpleNamespace(
            provider="mock",
            model="token-hash-v2",
            index_generation=1,
            space_id="mock:token-hash-v2:1536:g1",
        )

    def mark_ready(self, _actor_id: str) -> None:
        if self.ready_error:
            raise RuntimeError("state unavailable")

    def mark_failed(self, _actor_id: str, reason: str) -> None:
        self.failed.append(reason)
        if self.failed_error:
            raise RuntimeError("failure state unavailable")


class _Index:
    def __init__(self, *, begin_error: bool = False) -> None:
        self.begin_error = begin_error
        self.failed: list[tuple[UUID, str]] = []
        self.rolled_back: list[tuple[UUID, str]] = []
        self.activated = False
        self.recovered = 0

    def begin(self, _profile: SearchIndexProfile) -> None:
        if self.begin_error:
            raise RuntimeError("write unavailable")

    def activate(self, *_args: object) -> None:
        self.activated = True

    def fail(self, profile_id: UUID, reason: str) -> None:
        self.failed.append((profile_id, reason))

    def rollback_activation(self, profile_id: UUID, reason: str) -> None:
        self.rolled_back.append((profile_id, reason))

    def recover_interrupted(self) -> int:
        self.recovered += 1
        return 1


class _Embeddings:
    space_id = "mock:token-hash-v2:1536:g1"

    def __init__(self, result: tuple[tuple[float, ...], ...] | None = ()) -> None:
        self.result = result

    def embed_many(self, *_args: object, **_kwargs: object) -> tuple[tuple[float, ...], ...] | None:
        return self.result


class _ObjectStorage:
    def __init__(self, content: bytes = b"synthetic") -> None:
        self.content = content

    def exists(self, _key: str) -> bool:
        return True

    def read_bytes(self, _key: str) -> bytes:
        return self.content


def _service(
    configuration: _Configuration | None = None,
    index: _Index | None = None,
    embeddings: _Embeddings | None = None,
) -> SearchIndexingService:
    store = SimpleNamespace(repository=SimpleNamespace(list_products=lambda: ()))
    tickets = SimpleNamespace(tickets=SimpleNamespace(assignment_snapshot=lambda: ()))
    return SearchIndexingService(
        cast(Any, configuration or _Configuration()),
        cast(Any, embeddings or _Embeddings()),
        cast(Any, index or _Index()),
        cast(Any, store),
        cast(Any, _ObjectStorage()),
        cast(Any, tickets),
    )


def _profile(corpus_version: str) -> SearchIndexProfile:
    return SearchIndexProfile(
        profile_id=uuid4(),
        provider="mock",
        model="token-hash-v2",
        dimensions=SEARCH_EMBEDDING_DIMENSIONS,
        generation=1,
        space_id="mock:token-hash-v2:1536:g1",
        status="indexing",
        is_active=False,
        corpus_version=corpus_version,
        product_count=0,
        chunk_count=0,
        indexed_count=0,
        failed_count=0,
        created_by_user_id=uuid4(),
        created_at=datetime.now(UTC),
    )


def _chunk() -> SearchChunk:
    content = "synthetic evidence"
    return SearchChunk(
        chunk_id=uuid4(),
        product_id=uuid4(),
        asset_id=None,
        asset_name="Product metadata",
        asset_sha256=None,
        page_number=0,
        chunk_index=0,
        content=content,
        content_hash=sha256(content.encode()).hexdigest(),
        extractor_version="metadata-v1",
        chunker_version="test-v1",
    )


def test_start_marks_configuration_failed_when_index_begin_fails() -> None:
    configuration = _Configuration()
    service = _service(configuration, _Index(begin_error=True))

    with pytest.raises(RuntimeError, match="write unavailable"):
        service.start(uuid4())
    assert configuration.failed == ["index_write_failed"]


def test_startup_recovery_always_clears_stranded_repository_jobs() -> None:
    ready_index = _Index()
    assert _service(_Configuration(), ready_index).recover_interrupted() is True
    assert ready_index.recovered == 1

    configuration = _Configuration(index_status="indexing")
    interrupted_index = _Index()
    assert _service(configuration, interrupted_index).recover_interrupted() is True
    assert interrupted_index.recovered == 1
    assert configuration.failed == ["worker_interrupted"]


def test_run_handles_corpus_change_even_when_failure_state_cannot_persist() -> None:
    configuration = _Configuration(failed_error=True)
    index = _Index()
    service = _service(configuration, index)
    profile = _profile("changed-before-run")

    service.run(profile)

    assert index.failed == [(profile.profile_id, "corpus_changed")]
    assert configuration.failed == ["corpus_changed"]


def test_run_rolls_back_activation_when_ready_state_cannot_persist() -> None:
    configuration = _Configuration(ready_error=True)
    index = _Index()
    service = _service(configuration, index)
    profile = _profile(service.corpus_version())

    service.run(profile)

    assert index.activated is True
    assert index.rolled_back == [(profile.profile_id, "index_write_failed")]
    assert configuration.failed == ["index_write_failed"]


def test_run_rejects_incomplete_provider_result(monkeypatch: pytest.MonkeyPatch) -> None:
    configuration = _Configuration()
    index = _Index()
    service = _service(configuration, index)
    profile = _profile(service.corpus_version())
    monkeypatch.setattr(service, "_extract_chunks", lambda *_args: ((_chunk(),), ()))
    monkeypatch.setattr(service, "_embed_chunks", lambda _chunks, _space_id: ())

    service.run(profile)

    assert index.failed == [(profile.profile_id, "provider_unavailable")]
    assert configuration.failed == ["provider_unavailable"]


def test_embedding_helpers_stop_on_provider_failure() -> None:
    service = _service(embeddings=_Embeddings(None))
    chunk = _chunk()
    document = SearchTicketDocument(uuid4(), "RFI_SEARCHING", "request", "hash")

    assert service._embed_chunks((chunk,), "mock:test:1536:g1") == ()
    assert service._embed_tickets((document,), "mock:test:1536:g1") == ()


def test_product_corpus_hash_uses_index_inputs_not_lifecycle_timestamps() -> None:
    product = seed_product()
    initial = search_indexing._product_corpus_version((product,))
    timestamp_only = replace(product, updated_at=product.updated_at + timedelta(days=1))
    metadata_changed = replace(
        product,
        metadata=replace(product.metadata, summary="Changed indexed summary"),
    )
    asset_changed = replace(
        product,
        assets=(replace(product.assets[0], mime_type="application/x-test"),),
    )

    assert search_indexing._product_corpus_version((timestamp_only,)) == initial
    assert search_indexing._product_corpus_version((metadata_changed,)) != initial
    assert search_indexing._product_corpus_version((asset_changed,)) != initial


@pytest.mark.parametrize(
    ("code", "expected_status"),
    [("asset_type_unsupported", "unsupported"), ("pdf_parse_failed", "failed")],
)
def test_extraction_records_safe_asset_failure(
    monkeypatch: pytest.MonkeyPatch,
    code: str,
    expected_status: str,
) -> None:
    content = b"synthetic"
    asset = SimpleNamespace(
        asset_id=uuid4(),
        object_key="asset-key",
        sha256=sha256(content).hexdigest(),
        size_bytes=len(content),
        mime_type="application/pdf",
    )
    product = SimpleNamespace(product_id=uuid4(), assets=(asset,))
    service = _service()
    monkeypatch.setattr(search_indexing, "metadata_chunk", lambda _product: _chunk())
    monkeypatch.setattr(
        search_indexing,
        "extract_pages",
        lambda *_args: (_ for _ in ()).throw(DocumentExtractionError(code)),
    )

    _chunks, states = service._extract_chunks(uuid4(), cast(Any, (product,)))

    assert states[0].status == expected_status
    assert states[0].error_code == code
