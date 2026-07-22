"""Application composition for search indexing and retrieval services."""

from fastapi import FastAPI

from coeus.core.config import Settings
from coeus.persistence import search_index_postgres
from coeus.persistence.search_index_repository import (
    MemorySearchIndexRepository,
    SearchIndexRepository,
)
from coeus.services.audit import AuditLog
from coeus.services.grounded_search import GroundedSearchService
from coeus.services.search_configuration import SearchConfigurationService
from coeus.services.search_embeddings import SearchEmbeddingService
from coeus.services.search_indexing import SearchIndexingService


def build_search_index_repository(settings: Settings) -> SearchIndexRepository:
    if settings.persistence_provider == "postgres":
        return search_index_postgres.build_postgres_search_index(settings)
    return MemorySearchIndexRepository()


def configure_search_services(app: FastAPI, settings: Settings, audit_log: AuditLog) -> None:
    configuration = SearchConfigurationService(
        settings,
        audit_log,
        app.state.state_store,
        app.state.integration_secret_store,
    )
    embeddings = SearchEmbeddingService(settings, configuration, app.state.provider_admission)
    repository = build_search_index_repository(settings)
    indexing = SearchIndexingService(
        configuration,
        embeddings,
        repository,
        app.state.store_services,
        app.state.object_storage,
        app.state.ticket_services,
    )
    app.state.search_configuration_service = configuration
    app.state.search_embedding_service = embeddings
    app.state.search_index_repository = repository
    app.state.search_indexing_service = indexing
    app.state.grounded_search_service = GroundedSearchService(
        repository,
        configuration,
        embeddings,
        app.state.store_services,
        app.state.access_services.repository,
    )
    configuration.set_index_counts_provider(repository.counts)
    configuration.set_current_corpus_version_provider(indexing.corpus_version)
