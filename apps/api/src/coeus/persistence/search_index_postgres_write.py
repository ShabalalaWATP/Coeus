"""Atomic PostgreSQL writes for one complete search-index generation."""

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Connection

from coeus.domain.search_index import (
    SearchAssetIndexState,
    SearchChunk,
    SearchChunkEmbedding,
    SearchIndexProfile,
    SearchTicketDocument,
    SearchTicketEmbedding,
)
from coeus.persistence.search_index_repository import _vector
from coeus.persistence.search_index_sql import (
    ACTIVATE_PROFILE_SQL,
    INSERT_ASSET_INDEX_STATE_SQL,
    INSERT_EMBEDDING_SQL,
    INSERT_TICKET_EMBEDDING_SQL,
    UPSERT_CHUNK_SQL,
    UPSERT_TICKET_DOCUMENT_SQL,
)
from coeus.persistence.search_index_validation import validate_generation_inputs


def validate_generation(
    profile: SearchIndexProfile,
    chunks: tuple[SearchChunk, ...],
    embeddings: tuple[SearchChunkEmbedding, ...],
    ticket_documents: tuple[SearchTicketDocument, ...],
    ticket_embeddings: tuple[SearchTicketEmbedding, ...],
) -> None:
    validate_generation_inputs(profile, chunks, embeddings, ticket_documents, ticket_embeddings)


def write_generation(
    connection: Connection,
    profile: SearchIndexProfile,
    chunks: tuple[SearchChunk, ...],
    embeddings: tuple[SearchChunkEmbedding, ...],
    ticket_documents: tuple[SearchTicketDocument, ...],
    ticket_embeddings: tuple[SearchTicketEmbedding, ...],
    asset_states: tuple[SearchAssetIndexState, ...],
) -> None:
    _write_chunks(connection, profile, chunks, embeddings)
    _write_tickets(connection, profile, ticket_documents, ticket_embeddings)
    _write_asset_states(connection, asset_states)
    _promote(connection, profile, len(embeddings))


def _write_chunks(
    connection: Connection,
    profile: SearchIndexProfile,
    chunks: tuple[SearchChunk, ...],
    embeddings: tuple[SearchChunkEmbedding, ...],
) -> None:
    for chunk in chunks:
        connection.execute(text(UPSERT_CHUNK_SQL), _params(chunk))
    for embedding in embeddings:
        connection.execute(
            text(INSERT_EMBEDDING_SQL),
            {
                "profile_id": str(profile.profile_id),
                "chunk_id": str(embedding.chunk_id),
                "source_hash": embedding.source_hash,
                "embedding": _vector(embedding.vector),
            },
        )


def _write_tickets(
    connection: Connection,
    profile: SearchIndexProfile,
    documents: tuple[SearchTicketDocument, ...],
    embeddings: tuple[SearchTicketEmbedding, ...],
) -> None:
    for document in documents:
        connection.execute(
            text(UPSERT_TICKET_DOCUMENT_SQL),
            {**_params(document), "profile_id": str(profile.profile_id)},
        )
    for embedding in embeddings:
        connection.execute(
            text(INSERT_TICKET_EMBEDDING_SQL),
            {
                "profile_id": str(profile.profile_id),
                "ticket_id": str(embedding.ticket_id),
                "source_hash": embedding.source_hash,
                "embedding": _vector(embedding.vector),
            },
        )


def _write_asset_states(
    connection: Connection, asset_states: tuple[SearchAssetIndexState, ...]
) -> None:
    for asset_state in asset_states:
        connection.execute(text(INSERT_ASSET_INDEX_STATE_SQL), _params(asset_state))


def _promote(connection: Connection, profile: SearchIndexProfile, indexed_count: int) -> None:
    completed = connection.execute(
        text(ACTIVATE_PROFILE_SQL),
        {
            "profile_id": str(profile.profile_id),
            "product_count": profile.product_count,
            "chunk_count": profile.chunk_count,
            "indexed_count": indexed_count,
            "failed_count": profile.failed_count,
        },
    ).first()
    if completed is None:
        raise RuntimeError("search index candidate is not indexing")
    connection.execute(
        text(
            "UPDATE search_index_profiles SET is_active = false "
            "WHERE is_active AND profile_id <> CAST(:profile_id AS uuid)"
        ),
        {"profile_id": str(profile.profile_id)},
    )
    activated = connection.execute(
        text(
            "UPDATE search_index_profiles SET is_active = true "
            "WHERE profile_id = CAST(:profile_id AS uuid) AND status = 'ready' "
            "RETURNING profile_id"
        ),
        {"profile_id": str(profile.profile_id)},
    ).first()
    if activated is None:
        raise RuntimeError("search index candidate could not be activated")


def _params(value: object) -> dict[str, object]:
    return {key: str(item) if isinstance(item, UUID) else item for key, item in vars(value).items()}
