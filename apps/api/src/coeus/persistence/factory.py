from coeus.core.config import Settings
from coeus.persistence.audit_store import (
    AuditEventStore,
    FileAuditEventStore,
    MemoryAuditEventStore,
)
from coeus.persistence.state_store import (
    FileStateStore,
    MemoryStateStore,
    PostgresStateStore,
    StateStore,
)


def build_state_store(settings: Settings) -> StateStore:
    if settings.persistence_provider == "file":
        return FileStateStore(settings.persistence_path)
    if settings.persistence_provider == "postgres":
        return PostgresStateStore(settings.database_url)
    return MemoryStateStore()


def build_audit_event_store(settings: Settings, state_store: StateStore) -> AuditEventStore:
    if isinstance(state_store, PostgresStateStore):
        return state_store.audit_event_store()
    if isinstance(state_store, FileStateStore):
        return FileAuditEventStore(settings.audit_log_path)
    return MemoryAuditEventStore()
