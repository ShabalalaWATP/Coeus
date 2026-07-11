from coeus.persistence.state_store import PostgresStateStore, StateStore
from coeus.repositories.access import AccessRepository
from coeus.repositories.store import InMemoryStoreRepository
from coeus.services.asset_tokens import AssetTokenService
from coeus.services.audit import AuditLog
from coeus.services.embeddings import EmbeddingService
from coeus.services.store import StoreIngestionService, StoreSearchService, StoreServices
from coeus.services.store_access import StoreAssetService, StoreDetailService
from coeus.services.store_metadata_suggestions import MetadataSuggestionService
from coeus.services.store_product_policy import StoreProductAccessPolicy


def build_store_services(
    access_repository: AccessRepository,
    audit_log: AuditLog,
    asset_tokens: AssetTokenService,
    state_store: StateStore | None = None,
    embeddings: EmbeddingService | None = None,
) -> StoreServices:
    projection = (
        state_store.store_projection(embeddings)
        if isinstance(state_store, PostgresStateStore)
        else None
    )
    repository = InMemoryStoreRepository(access_repository, state_store, projection, embeddings)
    policy = StoreProductAccessPolicy(access_repository)
    details = StoreDetailService(repository, policy, audit_log)
    return StoreServices(
        repository=repository,
        ingestion=StoreIngestionService(repository, access_repository, audit_log),
        search=StoreSearchService(repository, policy, embeddings),
        details=details,
        assets=StoreAssetService(details, asset_tokens, audit_log),
        suggestions=MetadataSuggestionService(),
    )
