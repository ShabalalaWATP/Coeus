from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Response, status

from coeus.api.dependencies import (
    get_csrf_validated_session,
    require_permission,
)
from coeus.api.search_dependencies import (
    get_search_configuration_service,
    get_search_embedding_service,
    get_search_indexing_service,
)
from coeus.core.permissions import Permission
from coeus.domain.auth import AuthenticatedSession
from coeus.schemas.search_admin import (
    SearchEmbeddingConfigurationRequest,
    SearchEmbeddingKeyRequest,
    SearchEmbeddingStateResponse,
    SearchEmbeddingTestResponse,
)
from coeus.services.search_configuration import (
    SearchConfigurationService,
    SearchConfigurationState,
)
from coeus.services.search_embeddings import SearchEmbeddingService
from coeus.services.search_indexing import SearchIndexingService

router = APIRouter(prefix="/admin/search-embeddings", tags=["admin search"])


@router.get("", response_model=SearchEmbeddingStateResponse)
def search_embedding_state(
    authenticated: Annotated[
        AuthenticatedSession,
        Depends(require_permission(Permission.SYSTEM_CONFIGURE)),
    ],
    configuration: Annotated[SearchConfigurationService, Depends(get_search_configuration_service)],
) -> SearchEmbeddingStateResponse:
    del authenticated
    return _response(configuration.state())


@router.put("/api-key", response_model=SearchEmbeddingStateResponse)
def configure_search_embedding_key(
    payload: SearchEmbeddingKeyRequest,
    authenticated: Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)],
    permitted: Annotated[
        AuthenticatedSession,
        Depends(require_permission(Permission.SYSTEM_CONFIGURE)),
    ],
    configuration: Annotated[SearchConfigurationService, Depends(get_search_configuration_service)],
) -> SearchEmbeddingStateResponse:
    del permitted
    configuration.configure_key(
        str(authenticated.user.user_id), authenticated.user.username, payload.api_key
    )
    return _response(configuration.state())


@router.put("/configuration", response_model=SearchEmbeddingStateResponse)
def configure_search_embeddings(
    payload: SearchEmbeddingConfigurationRequest,
    authenticated: Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)],
    permitted: Annotated[
        AuthenticatedSession,
        Depends(require_permission(Permission.SYSTEM_CONFIGURE)),
    ],
    configuration: Annotated[SearchConfigurationService, Depends(get_search_configuration_service)],
) -> SearchEmbeddingStateResponse:
    del permitted
    return _response(
        configuration.configure(
            str(authenticated.user.user_id),
            authenticated.user.username,
            payload.provider,
            payload.model,
            payload.confirm_external_egress,
        )
    )


@router.post("/test", response_model=SearchEmbeddingTestResponse)
def test_search_embeddings(
    authenticated: Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)],
    permitted: Annotated[
        AuthenticatedSession,
        Depends(require_permission(Permission.SYSTEM_CONFIGURE)),
    ],
    configuration: Annotated[SearchConfigurationService, Depends(get_search_configuration_service)],
    embeddings: Annotated[SearchEmbeddingService, Depends(get_search_embedding_service)],
) -> SearchEmbeddingTestResponse:
    del permitted
    state = configuration.state()
    vector = embeddings.embed(
        "MOCK DATA ONLY Coeus retrieval connection test",
        purpose="test",
        principal_id=authenticated.user.user_id,
    )
    return SearchEmbeddingTestResponse(
        ok=vector is not None,
        provider=state.provider,
        model=state.model,
        message=(
            "Search embedding connection succeeded."
            if vector is not None
            else "Search embedding connection is unavailable."
        ),
    )


@router.post("/reindex", response_model=SearchEmbeddingStateResponse)
def reindex_search_embeddings(
    background_tasks: BackgroundTasks,
    response: Response,
    authenticated: Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)],
    permitted: Annotated[
        AuthenticatedSession,
        Depends(require_permission(Permission.SYSTEM_CONFIGURE)),
    ],
    configuration: Annotated[SearchConfigurationService, Depends(get_search_configuration_service)],
    indexing: Annotated[SearchIndexingService, Depends(get_search_indexing_service)],
) -> SearchEmbeddingStateResponse:
    del permitted
    profile = indexing.start(authenticated.user.user_id)
    background_tasks.add_task(indexing.run, profile)
    response.status_code = status.HTTP_202_ACCEPTED
    return _response(configuration.state())


def _response(state: SearchConfigurationState) -> SearchEmbeddingStateResponse:
    return SearchEmbeddingStateResponse(
        provider=state.provider,
        model=state.model,
        dimensions=state.dimensions,
        api_key_configured=state.api_key_configured,
        available_providers=list(state.available_providers),
        available_models=list(state.available_models),
        index_status=state.index_status,
        index_generation=state.index_generation,
        product_count=state.product_count,
        chunk_count=state.chunk_count,
        ticket_count=state.ticket_count,
        failed_asset_count=state.failed_asset_count,
        corpus_version=state.corpus_version,
        space_id=state.space_id,
        changed_by=state.changed_by,
        changed_at=state.changed_at,
        last_indexed_at=state.last_indexed_at,
        degraded_reason=state.degraded_reason,
        release_id=state.release_id,
        evaluation_status=state.evaluation_status,
        definitive_no_match_enabled=state.definitive_no_match_enabled,
    )
