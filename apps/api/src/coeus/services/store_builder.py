from coeus.persistence.state_store import PostgresStateStore, StateStore
from coeus.repositories.access import SeedAccessRepository
from coeus.repositories.store import InMemoryStoreRepository
from coeus.services.asset_tokens import AssetTokenService
from coeus.services.audit import AuditLog
from coeus.services.store import (
    MetadataSuggestionService,
    StoreIngestionService,
    StoreProductAccessPolicy,
    StoreSearchService,
    StoreServices,
)
from coeus.services.store_access import StoreAssetService, StoreDetailService


def build_store_services(
    access_repository: SeedAccessRepository,
    audit_log: AuditLog,
    asset_tokens: AssetTokenService,
    state_store: StateStore | None = None,
) -> StoreServices:
    projection = (
        state_store.store_projection() if isinstance(state_store, PostgresStateStore) else None
    )
    repository = InMemoryStoreRepository(access_repository, state_store, projection)
    policy = StoreProductAccessPolicy(access_repository)
    details = StoreDetailService(repository, policy, audit_log)
    return StoreServices(
        repository=repository,
        ingestion=StoreIngestionService(repository, access_repository, audit_log),
        search=StoreSearchService(repository, policy),
        details=details,
        assets=StoreAssetService(details, asset_tokens, audit_log),
        suggestions=MetadataSuggestionService(),
    )
