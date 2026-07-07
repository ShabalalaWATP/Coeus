from coeus.core.config import Settings
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
