"""Pre-write integrity checks for one complete search-index generation."""

from hashlib import sha256
from math import isfinite

from coeus.domain.search_index import (
    SEARCH_EMBEDDING_DIMENSIONS,
    SearchChunk,
    SearchChunkEmbedding,
    SearchIndexProfile,
    SearchTicketDocument,
    SearchTicketEmbedding,
)


def validate_generation_inputs(
    profile: SearchIndexProfile,
    chunks: tuple[SearchChunk, ...],
    embeddings: tuple[SearchChunkEmbedding, ...],
    ticket_documents: tuple[SearchTicketDocument, ...],
    ticket_embeddings: tuple[SearchTicketEmbedding, ...],
) -> None:
    chunk_hashes = {chunk.chunk_id: chunk.content_hash for chunk in chunks}
    embedding_ids = [chunk_embedding.chunk_id for chunk_embedding in embeddings]
    if len(chunk_hashes) != len(chunks) or len(set(embedding_ids)) != len(embeddings):
        raise ValueError("Search chunk identities must be unique within a generation.")
    if set(chunk_hashes) != set(embedding_ids):
        raise ValueError("Every search chunk must have exactly one matching embedding.")
    if any(
        chunk_embedding.source_hash
        != embedding_source_hash(profile.space_id, chunk_hashes[chunk_embedding.chunk_id])
        for chunk_embedding in embeddings
    ):
        raise ValueError("Search chunk embeddings must match their source content.")
    for chunk_embedding in embeddings:
        validate_vector(chunk_embedding.vector)

    ticket_hashes = {document.ticket_id: document.content_hash for document in ticket_documents}
    ticket_embedding_ids = [ticket_embedding.ticket_id for ticket_embedding in ticket_embeddings]
    if len(ticket_hashes) != len(ticket_documents) or len(set(ticket_embedding_ids)) != len(
        ticket_embeddings
    ):
        raise ValueError("Search ticket identities must be unique within a generation.")
    if set(ticket_hashes) != set(ticket_embedding_ids):
        raise ValueError("Every search ticket must have exactly one matching embedding.")
    if any(
        ticket_embedding.source_hash
        != embedding_source_hash(profile.space_id, ticket_hashes[ticket_embedding.ticket_id])
        for ticket_embedding in ticket_embeddings
    ):
        raise ValueError("Search ticket embeddings must match their source content.")
    for ticket_embedding in ticket_embeddings:
        validate_vector(ticket_embedding.vector)


def embedding_source_hash(space_id: str, content_hash: str) -> str:
    return sha256(f"{space_id}\n{content_hash}".encode()).hexdigest()


def validate_vector(value: tuple[float, ...]) -> None:
    if len(value) != SEARCH_EMBEDDING_DIMENSIONS or any(not isfinite(item) for item in value):
        raise ValueError("Search vectors must contain 1,536 finite dimensions.")
