from fastapi import FastAPI

from coeus.core.config import Settings
from coeus.persistence.search_index_repository import build_search_index_repository
from coeus.services.audit import AuditLog
from coeus.services.grounded_search import GroundedSearchService
from coeus.services.search_configuration import SearchConfigurationService
from coeus.services.search_embeddings import SearchEmbeddingService
from coeus.services.search_indexing import SearchIndexingService


def configure_search_services(app: FastAPI, settings: Settings, audit_log: AuditLog) -> None:
    configuration = SearchConfigurationService(
        settings,
        audit_log,
        app.state.state_store,
        app.state.integration_secret_store,
    )
    embeddings = SearchEmbeddingService(settings, configuration, app.state.provider_admission)
    repository = build_search_index_repository(settings)
    app.state.search_configuration_service = configuration
    app.state.search_embedding_service = embeddings
    app.state.search_index_repository = repository
    app.state.search_indexing_service = SearchIndexingService(
        configuration,
        embeddings,
        repository,
        app.state.store_services,
        app.state.object_storage,
        app.state.ticket_services,
    )
    app.state.grounded_search_service = GroundedSearchService(
        repository,
        configuration,
        embeddings,
        app.state.store_services,
        app.state.access_services.repository,
    )
    configuration.set_index_counts_provider(repository.counts)
    configuration.set_current_corpus_version_provider(
        app.state.search_indexing_service.corpus_version
    )
