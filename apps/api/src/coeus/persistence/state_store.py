import json
from pathlib import Path
from threading import RLock
from typing import TYPE_CHECKING, Any, Protocol

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from coeus.persistence.relational_schema import ensure_relational_schema

if TYPE_CHECKING:
    from coeus.persistence.store_projection import PostgresStoreProjection
    from coeus.services.embeddings import EmbeddingService


class StateStore(Protocol):
    def load(self, namespace: str) -> dict[str, Any] | None:
        raise NotImplementedError

    def save(self, namespace: str, payload: dict[str, Any]) -> None:
        raise NotImplementedError


class MemoryStateStore:
    def __init__(self) -> None:
        self._state: dict[str, dict[str, Any]] = {}

    def load(self, namespace: str) -> dict[str, Any] | None:
        return self._state.get(namespace)

    def save(self, namespace: str, payload: dict[str, Any]) -> None:
        self._state[namespace] = payload


class FileStateStore:
    def __init__(self, path: Path | str) -> None:
        self._path = Path(path)
        self._lock = RLock()

    def load(self, namespace: str) -> dict[str, Any] | None:
        with self._lock:
            state = self._read()
            payload = state.get(namespace)
            return payload if isinstance(payload, dict) else None

    def save(self, namespace: str, payload: dict[str, Any]) -> None:
        with self._lock:
            state = self._read()
            state[namespace] = payload
            self._path.parent.mkdir(parents=True, exist_ok=True)
            temp_path = self._path.with_suffix(f"{self._path.suffix}.tmp")
            temp_path.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
            temp_path.replace(self._path)

    def _read(self) -> dict[str, Any]:
        if not self._path.exists():
            return {}
        try:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"State file {self._path} is not valid JSON.") from exc
        if not isinstance(payload, dict):
            raise ValueError(f"State file {self._path} must contain a JSON object.")
        return payload


class PostgresStateStore:
    def __init__(self, database_url: str) -> None:
        self._engine = create_engine(_sync_database_url(database_url), pool_pre_ping=True)
        self._schema_ready = False
        self._lock = RLock()

    def load(self, namespace: str) -> dict[str, Any] | None:
        with self._lock:
            self._ensure_schema()
            with self._engine.begin() as connection:
                row = connection.execute(
                    text("SELECT payload FROM coeus_state WHERE namespace = :namespace"),
                    {"namespace": namespace},
                ).first()
            return dict(row[0]) if row is not None else None

    def save(self, namespace: str, payload: dict[str, Any]) -> None:
        with self._lock:
            self._ensure_schema()
            with self._engine.begin() as connection:
                connection.execute(
                    text(
                        """
                        INSERT INTO coeus_state(namespace, payload, updated_at)
                        VALUES (:namespace, CAST(:payload AS jsonb), now())
                        ON CONFLICT (namespace)
                        DO UPDATE SET payload = EXCLUDED.payload, updated_at = now()
                        """
                    ),
                    {"namespace": namespace, "payload": json.dumps(payload)},
                )

    def store_projection(
        self, embeddings: "EmbeddingService | None" = None
    ) -> "PostgresStoreProjection":
        from coeus.persistence.store_projection import PostgresStoreProjection

        self._ensure_schema()
        return PostgresStoreProjection(self._engine, embeddings)

    def _ensure_schema(self) -> None:
        if self._schema_ready:
            return
        try:
            with self._engine.begin() as connection:
                connection.execute(
                    text(
                        """
                        CREATE TABLE IF NOT EXISTS coeus_state (
                            namespace text PRIMARY KEY,
                            payload jsonb NOT NULL,
                            updated_at timestamptz NOT NULL DEFAULT now()
                        )
                        """
                    )
                )
                ensure_relational_schema(connection)
        except SQLAlchemyError as exc:
            raise RuntimeError("Could not initialise local persistence store.") from exc
        self._schema_ready = True


def _sync_database_url(database_url: str) -> str:
    if database_url.startswith("postgresql+asyncpg://"):
        return database_url.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)
    return database_url
