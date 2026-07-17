from fastapi import Request

from coeus.core.errors import AppError
from coeus.services.search_configuration import SearchConfigurationService
from coeus.services.search_embeddings import SearchEmbeddingService
from coeus.services.search_indexing import SearchIndexingService


def get_search_configuration_service(request: Request) -> SearchConfigurationService:
    service = getattr(request.app.state, "search_configuration_service", None)
    if not isinstance(service, SearchConfigurationService):
        raise AppError(500, "search_not_configured", "Search configuration is not available.")
    return service


def get_search_embedding_service(request: Request) -> SearchEmbeddingService:
    service = getattr(request.app.state, "search_embedding_service", None)
    if not isinstance(service, SearchEmbeddingService):
        raise AppError(500, "search_not_configured", "Search embeddings are not available.")
    return service


def get_search_indexing_service(request: Request) -> SearchIndexingService:
    service = getattr(request.app.state, "search_indexing_service", None)
    if not isinstance(service, SearchIndexingService):
        raise AppError(500, "search_not_configured", "Search indexing is not available.")
    return service
