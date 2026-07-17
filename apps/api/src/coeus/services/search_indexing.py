"""Build a shadow search generation and promote it only when complete."""

from dataclasses import replace
from datetime import UTC, datetime
from hashlib import sha256
from uuid import UUID, uuid4

from coeus.application.ports.embeddings import EMBEDDING_WORKLOAD_PRINCIPAL
from coeus.core.logging import get_logger
from coeus.domain.access import ProductStatus
from coeus.domain.search_index import (
    SEARCH_EMBEDDING_DIMENSIONS,
    SearchAssetIndexState,
    SearchChunk,
    SearchChunkEmbedding,
    SearchIndexProfile,
    SearchTicketDocument,
    SearchTicketEmbedding,
)
from coeus.domain.store import StoreAsset, StoreProduct
from coeus.domain.tickets import TicketRecord
from coeus.persistence.search_index_repository import SearchIndexRepository
from coeus.services.document_extraction import DocumentExtractionError, extract_pages
from coeus.services.object_storage import ObjectStorage
from coeus.services.rfi_ranking import query_text
from coeus.services.search_chunking import document_chunks, metadata_chunk
from coeus.services.search_configuration import SearchConfigurationService
from coeus.services.search_embeddings import SearchEmbeddingService
from coeus.services.similar_request_scoring import OPEN_SIMILARITY_STATES
from coeus.services.store import StoreServices
from coeus.services.tickets import TicketServices

EMBEDDING_BATCH_SIZE = 100
logger = get_logger(__name__)


class SearchIndexingService:
    def __init__(
        self,
        configuration: SearchConfigurationService,
        embeddings: SearchEmbeddingService,
        index: SearchIndexRepository,
        store: StoreServices,
        object_storage: ObjectStorage,
        tickets: TicketServices,
    ) -> None:
        self._configuration = configuration
        self._embeddings = embeddings
        self._index = index
        self._store = store
        self._object_storage = object_storage
        self._tickets = tickets

    def corpus_version(self) -> str:
        return _corpus_version(self._eligible_products(), self._eligible_tickets())

    def start(self, actor_id: UUID) -> SearchIndexProfile:
        state = self._configuration.mark_indexing(str(actor_id))
        products = self._eligible_products()
        tickets = self._eligible_tickets()
        profile = SearchIndexProfile(
            profile_id=uuid4(),
            provider=state.provider,
            model=state.model,
            dimensions=SEARCH_EMBEDDING_DIMENSIONS,
            generation=state.index_generation,
            space_id=state.space_id,
            status="indexing",
            is_active=False,
            corpus_version=_corpus_version(products, tickets),
            product_count=len(products),
            chunk_count=0,
            indexed_count=0,
            failed_count=0,
            created_by_user_id=actor_id,
            created_at=datetime.now(UTC),
        )
        try:
            self._index.begin(profile)
        except Exception:
            self._configuration.mark_failed(str(actor_id), "index_write_failed")
            raise
        return profile

    def run(self, profile: SearchIndexProfile) -> None:
        activated = False
        try:
            products = self._eligible_products()
            tickets = self._eligible_tickets()
            if _corpus_version(products, tickets) != profile.corpus_version:
                raise RuntimeError("corpus_changed")
            chunks, asset_states = self._extract_chunks(profile.profile_id, products)
            embeddings = self._embed_chunks(chunks)
            ticket_documents = _ticket_documents(tickets)
            ticket_embeddings = self._embed_tickets(ticket_documents)
            if len(embeddings) != len(chunks) or len(ticket_embeddings) != len(ticket_documents):
                raise RuntimeError("provider_unavailable")
            if (
                _corpus_version(self._eligible_products(), self._eligible_tickets())
                != profile.corpus_version
            ):
                raise RuntimeError("corpus_changed")
            completed = replace(
                profile,
                status="ready",
                is_active=True,
                chunk_count=len(chunks),
                indexed_count=len(embeddings),
                failed_count=sum(state.status != "indexed" for state in asset_states),
                completed_at=datetime.now(UTC),
            )
            self._index.activate(
                completed,
                chunks,
                embeddings,
                ticket_documents,
                ticket_embeddings,
                asset_states,
            )
            activated = True
            self._configuration.mark_ready(str(profile.created_by_user_id))
        except Exception as exc:
            code = (
                str(exc)
                if str(exc) in {"corpus_changed", "provider_unavailable"}
                else "index_write_failed"
            )
            if activated:
                self._index.rollback_activation(profile.profile_id, code)
            else:
                self._index.fail(profile.profile_id, code)
            try:
                self._configuration.mark_failed(str(profile.created_by_user_id), code)
            except Exception:
                logger.exception(
                    "search_index_failure_state_persist_failed",
                    extra={"profile_id": str(profile.profile_id)},
                )

    def _eligible_products(self) -> tuple[StoreProduct, ...]:
        return tuple(
            product
            for product in self._store.repository.list_products()
            if product.metadata.status == ProductStatus.PUBLISHED
            and product.metadata.releasability == frozenset({"MOCK"})
            and product.metadata.handling_caveats == frozenset({"MOCK DATA ONLY"})
        )

    def _eligible_tickets(self) -> tuple[TicketRecord, ...]:
        return tuple(
            ticket
            for ticket in self._tickets.tickets.assignment_snapshot()
            if ticket.state in OPEN_SIMILARITY_STATES
        )

    def _extract_chunks(
        self, profile_id: UUID, products: tuple[StoreProduct, ...]
    ) -> tuple[tuple[SearchChunk, ...], tuple[SearchAssetIndexState, ...]]:
        chunks: list[SearchChunk] = []
        asset_states: list[SearchAssetIndexState] = []
        for product in products:
            chunks.append(metadata_chunk(product))
            for asset in product.assets:
                if not self._object_storage.exists(asset.object_key):
                    asset_states.append(
                        _asset_state(profile_id, product, asset, "failed", "object_missing")
                    )
                    continue
                content = self._object_storage.read_bytes(asset.object_key)
                if sha256(content).hexdigest() != asset.sha256 or len(content) != asset.size_bytes:
                    asset_states.append(
                        _asset_state(profile_id, product, asset, "failed", "integrity_mismatch")
                    )
                    continue
                try:
                    pages = extract_pages(content, asset.mime_type)
                except DocumentExtractionError as exc:
                    status = "unsupported" if exc.code == "asset_type_unsupported" else "failed"
                    asset_states.append(_asset_state(profile_id, product, asset, status, exc.code))
                    continue
                asset_chunks = document_chunks(product, asset, pages)
                chunks.extend(asset_chunks)
                asset_states.append(
                    _asset_state(
                        profile_id,
                        product,
                        asset,
                        "indexed" if asset_chunks else "failed",
                        None if asset_chunks else "no_extractable_text",
                        page_count=len(pages),
                        chunk_count=len(asset_chunks),
                    )
                )
        return tuple(chunks), tuple(asset_states)

    def _embed_chunks(self, chunks: tuple[SearchChunk, ...]) -> tuple[SearchChunkEmbedding, ...]:
        records: list[SearchChunkEmbedding] = []
        for start in range(0, len(chunks), EMBEDDING_BATCH_SIZE):
            batch = chunks[start : start + EMBEDDING_BATCH_SIZE]
            vectors = self._embeddings.embed_many(
                tuple(chunk.content for chunk in batch),
                principal_id=EMBEDDING_WORKLOAD_PRINCIPAL,
            )
            if vectors is None:
                return ()
            records.extend(
                SearchChunkEmbedding(
                    chunk_id=chunk.chunk_id,
                    source_hash=sha256(
                        f"{self._embeddings.space_id}\n{chunk.content_hash}".encode()
                    ).hexdigest(),
                    vector=vector,
                )
                for chunk, vector in zip(batch, vectors, strict=True)
            )
        return tuple(records)

    def _embed_tickets(
        self, documents: tuple[SearchTicketDocument, ...]
    ) -> tuple[SearchTicketEmbedding, ...]:
        records: list[SearchTicketEmbedding] = []
        for start in range(0, len(documents), EMBEDDING_BATCH_SIZE):
            batch = documents[start : start + EMBEDDING_BATCH_SIZE]
            vectors = self._embeddings.embed_many(
                tuple(document.content for document in batch),
                principal_id=EMBEDDING_WORKLOAD_PRINCIPAL,
            )
            if vectors is None:
                return ()
            records.extend(
                SearchTicketEmbedding(
                    ticket_id=document.ticket_id,
                    source_hash=sha256(
                        f"{self._embeddings.space_id}\n{document.content_hash}".encode()
                    ).hexdigest(),
                    vector=vector,
                )
                for document, vector in zip(batch, vectors, strict=True)
            )
        return tuple(records)


def _corpus_version(products: tuple[StoreProduct, ...], tickets: tuple[TicketRecord, ...]) -> str:
    digest = sha256()
    for product in sorted(products, key=lambda item: str(item.product_id)):
        digest.update(str(product.product_id).encode())
        digest.update(product.updated_at.isoformat().encode())
        for asset in product.assets:
            digest.update(asset.sha256.encode())
    for ticket in sorted(tickets, key=lambda item: str(item.ticket_id)):
        digest.update(str(ticket.ticket_id).encode())
        digest.update(ticket.updated_at.isoformat().encode())
    return digest.hexdigest()[:24]


def _ticket_documents(tickets: tuple[TicketRecord, ...]) -> tuple[SearchTicketDocument, ...]:
    documents = []
    for ticket in tickets:
        route = ticket.analyst_assignments[-1].route.value if ticket.analyst_assignments else ""
        team = ticket.analyst_assignments[-1].team_name if ticket.analyst_assignments else ""
        content = f"{query_text(ticket.intake)} route {route} team {team or ''}"[:32_000]
        documents.append(
            SearchTicketDocument(
                ticket_id=ticket.ticket_id,
                state=ticket.state.value,
                content=content,
                content_hash=sha256(content.encode()).hexdigest(),
            )
        )
    return tuple(documents)


def _asset_state(
    profile_id: UUID,
    product: StoreProduct,
    asset: StoreAsset,
    status: str,
    error_code: str | None,
    *,
    page_count: int = 0,
    chunk_count: int = 0,
) -> SearchAssetIndexState:
    return SearchAssetIndexState(
        profile_id=profile_id,
        product_id=product.product_id,
        asset_id=asset.asset_id,
        asset_sha256=asset.sha256,
        status=status,
        page_count=page_count,
        chunk_count=chunk_count,
        error_code=error_code,
    )
