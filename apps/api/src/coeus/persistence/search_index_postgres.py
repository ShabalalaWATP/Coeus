"""PostgreSQL persistence for the generation-aware grounded search index."""

from uuid import UUID

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from coeus.core.config import Settings
from coeus.domain.search_index import (
    GroundedProductEvidence,
    SearchAssetIndexState,
    SearchChunk,
    SearchChunkEmbedding,
    SearchIndexProfile,
    SearchTicketDocument,
    SearchTicketEmbedding,
    SearchTicketHit,
)
from coeus.domain.store import StoreVisibilityScope
from coeus.persistence.database_url import synchronous_database_url
from coeus.persistence.relational_schema import ensure_relational_schema
from coeus.persistence.search_index_repository import (
    SEARCH_LEG_LIMIT,
    SearchIndexRepository,
    _group_rows,
    _validate_vector,
    _vector,
)
from coeus.persistence.search_index_sql import (
    ACTIVATE_PROFILE_SQL,
    INSERT_ASSET_INDEX_STATE_SQL,
    INSERT_EMBEDDING_SQL,
    INSERT_PROFILE_SQL,
    INSERT_TICKET_EMBEDDING_SQL,
    SEARCH_CHUNKS_SQL,
    SEARCH_TICKETS_SQL,
    UPSERT_CHUNK_SQL,
    UPSERT_TICKET_DOCUMENT_SQL,
)


class PostgresSearchIndexRepository:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def begin(self, profile: SearchIndexProfile) -> None:
        with self._engine.begin() as connection:
            ensure_relational_schema(connection)
            active_job = connection.execute(
                text("SELECT 1 FROM search_index_profiles WHERE status = 'indexing' LIMIT 1")
            ).first()
            if active_job is not None:
                raise RuntimeError("search index is already running")
            connection.execute(text(INSERT_PROFILE_SQL), _dataclass_params(profile))

    def activate(
        self,
        profile: SearchIndexProfile,
        chunks: tuple[SearchChunk, ...],
        embeddings: tuple[SearchChunkEmbedding, ...],
        ticket_documents: tuple[SearchTicketDocument, ...] = (),
        ticket_embeddings: tuple[SearchTicketEmbedding, ...] = (),
        asset_states: tuple[SearchAssetIndexState, ...] = (),
    ) -> None:
        if len(chunks) != len(embeddings):
            raise ValueError("Every search chunk must have exactly one embedding.")
        for chunk_embedding in embeddings:
            _validate_vector(chunk_embedding.vector)
        if len(ticket_documents) != len(ticket_embeddings):
            raise ValueError("Every search ticket must have exactly one embedding.")
        for ticket_embedding in ticket_embeddings:
            _validate_vector(ticket_embedding.vector)
        with self._engine.begin() as connection:
            ensure_relational_schema(connection)
            for chunk in chunks:
                connection.execute(text(UPSERT_CHUNK_SQL), _dataclass_params(chunk))
            for chunk_embedding in embeddings:
                connection.execute(
                    text(INSERT_EMBEDDING_SQL),
                    {
                        "profile_id": str(profile.profile_id),
                        "chunk_id": str(chunk_embedding.chunk_id),
                        "source_hash": chunk_embedding.source_hash,
                        "embedding": _vector(chunk_embedding.vector),
                    },
                )
            for document in ticket_documents:
                connection.execute(text(UPSERT_TICKET_DOCUMENT_SQL), _dataclass_params(document))
            for ticket_embedding in ticket_embeddings:
                connection.execute(
                    text(INSERT_TICKET_EMBEDDING_SQL),
                    {
                        "profile_id": str(profile.profile_id),
                        "ticket_id": str(ticket_embedding.ticket_id),
                        "source_hash": ticket_embedding.source_hash,
                        "embedding": _vector(ticket_embedding.vector),
                    },
                )
            for asset_state in asset_states:
                connection.execute(
                    text(INSERT_ASSET_INDEX_STATE_SQL),
                    _dataclass_params(asset_state),
                )
            connection.execute(text("UPDATE search_index_profiles SET is_active = false"))
            connection.execute(
                text(ACTIVATE_PROFILE_SQL),
                {
                    "profile_id": str(profile.profile_id),
                    "product_count": profile.product_count,
                    "chunk_count": profile.chunk_count,
                    "indexed_count": len(embeddings),
                    "failed_count": profile.failed_count,
                },
            )

    def fail(self, profile_id: UUID, error_code: str) -> None:
        with self._engine.begin() as connection:
            ensure_relational_schema(connection)
            connection.execute(
                text(
                    "UPDATE search_index_profiles SET status = 'failed', "
                    "error_code = :error_code, completed_at = now() "
                    "WHERE profile_id = CAST(:profile_id AS uuid) AND status = 'indexing'"
                ),
                {"profile_id": str(profile_id), "error_code": error_code[:64]},
            )

    def rollback_activation(self, profile_id: UUID, error_code: str) -> None:
        with self._engine.begin() as connection:
            ensure_relational_schema(connection)
            connection.execute(
                text(
                    "UPDATE search_index_profiles SET status = 'failed', is_active = false, "
                    "error_code = :error_code, completed_at = now() "
                    "WHERE profile_id = CAST(:profile_id AS uuid)"
                ),
                {"profile_id": str(profile_id), "error_code": error_code[:64]},
            )
            connection.execute(
                text(
                    "UPDATE search_index_profiles SET is_active = true "
                    "WHERE profile_id = (SELECT profile_id FROM search_index_profiles "
                    "WHERE status = 'ready' AND profile_id <> CAST(:profile_id AS uuid) "
                    "ORDER BY completed_at DESC NULLS LAST LIMIT 1)"
                ),
                {"profile_id": str(profile_id)},
            )

    def counts(self) -> tuple[int, int, int, int, str]:
        with self._engine.begin() as connection:
            ensure_relational_schema(connection)
            row = connection.execute(
                text(
                    "SELECT profile.product_count, profile.chunk_count, "
                    "(SELECT count(*) FROM ticket_search_embeddings ticket "
                    " WHERE ticket.profile_id = profile.profile_id), "
                    "profile.failed_count, profile.corpus_version "
                    "FROM search_index_profiles profile WHERE profile.is_active"
                )
            ).first()
        return (
            (0, 0, 0, 0, "unindexed")
            if row is None
            else (int(row[0]), int(row[1]), int(row[2]), int(row[3]), str(row[4]))
        )

    def search(
        self,
        scope: StoreVisibilityScope,
        query: str,
        query_vector: tuple[float, ...] | None,
        allowed_product_ids: frozenset[UUID] | None = None,
    ) -> tuple[GroundedProductEvidence, ...]:
        del allowed_product_ids
        if not scope.acg_ids:
            return ()
        params = {
            "acg_ids": [str(item) for item in scope.acg_ids],
            "clearance_level": scope.clearance_level,
            "published_status": "published",
            "query": query.strip() or None,
            "query_embedding": _vector(query_vector),
            "leg_limit": SEARCH_LEG_LIMIT,
        }
        with self._engine.begin() as connection:
            ensure_relational_schema(connection)
            rows = tuple(
                dict(row) for row in connection.execute(text(SEARCH_CHUNKS_SQL), params).mappings()
            )
        return _group_rows(rows)

    def search_tickets(
        self,
        query: str,
        query_vector: tuple[float, ...] | None,
        allowed_ticket_ids: frozenset[UUID],
        states: frozenset[str],
    ) -> tuple[SearchTicketHit, ...]:
        if not allowed_ticket_ids:
            return ()
        params = {
            "ticket_ids": [str(item) for item in allowed_ticket_ids],
            "states": sorted(states),
            "query": query.strip() or None,
            "query_embedding": _vector(query_vector),
            "leg_limit": SEARCH_LEG_LIMIT,
        }
        with self._engine.begin() as connection:
            ensure_relational_schema(connection)
            rows = connection.execute(text(SEARCH_TICKETS_SQL), params).mappings()
            return tuple(
                SearchTicketHit(
                    UUID(str(row["ticket_id"])),
                    _optional_int(row["lexical_rank"]),
                    _optional_int(row["vector_rank"]),
                    float(row["lexical_score"] or 0),
                    float(row["vector_score"] or 0),
                )
                for row in rows
            )


def build_postgres_search_index(settings: Settings) -> SearchIndexRepository:
    engine = create_engine(synchronous_database_url(settings.database_url), pool_pre_ping=True)
    return PostgresSearchIndexRepository(engine)


def _dataclass_params(
    value: SearchIndexProfile | SearchChunk | SearchTicketDocument | SearchAssetIndexState,
) -> dict[str, object]:
    return {key: str(item) if isinstance(item, UUID) else item for key, item in vars(value).items()}


def _optional_int(value: object) -> int | None:
    return None if value is None else int(str(value))
