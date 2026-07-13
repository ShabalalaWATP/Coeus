import json
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from threading import RLock
from typing import TYPE_CHECKING, Any, Protocol
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from coeus.persistence.relational_schema import ensure_relational_schema

if TYPE_CHECKING:
    from coeus.persistence.audit_store import PostgresAuditEventStore
    from coeus.persistence.store_projection import PostgresStoreProjection
    from coeus.services.embeddings import EmbeddingService


class StateStore(Protocol):
    def load(self, namespace: str) -> dict[str, Any] | None:
        pass

    def save(self, namespace: str, payload: dict[str, Any]) -> None:
        pass


class MemoryStateStore:
    def __init__(self) -> None:
        self._state: dict[str, dict[str, Any]] = {}

    def load(self, namespace: str) -> dict[str, Any] | None:
        payload = self._state.get(namespace)
        return deepcopy(payload) if payload is not None else None

    def save(self, namespace: str, payload: dict[str, Any]) -> None:
        self._state[namespace] = deepcopy(payload)


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
    def __init__(self, database_url: str, ticket_mode: str = "shadow_validate") -> None:
        self._engine = create_engine(_sync_database_url(database_url), pool_pre_ping=True)
        self._ticket_mode = ticket_mode
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
            payload = dict(row[0]) if row is not None else None
            if namespace == "tickets" and payload is not None and self._ticket_mode != "legacy":
                _validate_ticket_shadow(self._engine, payload)
            return payload

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
                if namespace == "tickets":
                    _shadow_ticket_payload(connection, payload)

    def store_projection(
        self, embeddings: "EmbeddingService | None" = None
    ) -> "PostgresStoreProjection":
        from coeus.persistence.store_projection import PostgresStoreProjection

        self._ensure_schema()
        return PostgresStoreProjection(self._engine, embeddings)

    def audit_event_store(self) -> "PostgresAuditEventStore":
        from coeus.persistence.audit_store import PostgresAuditEventStore

        self._ensure_schema()
        return PostgresAuditEventStore(self._engine)

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
                _ensure_ticket_shadow_schema(connection)
                count = connection.execute(
                    text("SELECT count(*) FROM coeus_ticket_aggregates")
                ).scalar_one()
                legacy = connection.execute(
                    text("SELECT payload FROM coeus_state WHERE namespace = 'tickets'")
                ).scalar_one_or_none()
                if count == 0 and legacy is not None:
                    _shadow_ticket_payload(connection, dict(legacy))
        except SQLAlchemyError as exc:
            raise RuntimeError("Could not initialise local persistence store.") from exc
        self._schema_ready = True


def _sync_database_url(database_url: str) -> str:
    if database_url.startswith("postgresql+asyncpg://"):
        return database_url.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)
    return database_url


def _shadow_ticket_payload(connection: Any, payload: dict[str, Any]) -> None:
    """Shadow the authoritative namespace into versioned per-ticket rows."""
    tickets = payload.get("tickets", [])
    ticket_ids: list[str] = []
    for ticket in tickets if isinstance(tickets, list) else []:
        try:
            ticket_id = ticket["fields"]["ticket_id"]["__uuid__"]
        except (KeyError, TypeError):
            continue
        ticket_ids.append(ticket_id)
        serialised = json.dumps(ticket, sort_keys=True, separators=(",", ":"))
        canonical_hash = sha256(serialised.encode("utf-8")).hexdigest()
        row = connection.execute(
            text(
                """
                INSERT INTO coeus_ticket_aggregates(
                  ticket_id, version, payload, canonical_hash, updated_at
                ) VALUES (
                  CAST(:ticket_id AS uuid), 1, CAST(:payload AS jsonb), :canonical_hash, now()
                )
                ON CONFLICT (ticket_id) DO UPDATE SET
                  version = CASE
                    WHEN coeus_ticket_aggregates.canonical_hash <> EXCLUDED.canonical_hash
                    THEN coeus_ticket_aggregates.version + 1
                    ELSE coeus_ticket_aggregates.version
                  END,
                  payload = EXCLUDED.payload,
                  canonical_hash = EXCLUDED.canonical_hash,
                  updated_at = CASE
                    WHEN coeus_ticket_aggregates.canonical_hash <> EXCLUDED.canonical_hash
                    THEN now()
                    ELSE coeus_ticket_aggregates.updated_at
                  END
                RETURNING version
                """
            ),
            {
                "ticket_id": ticket_id,
                "payload": serialised,
                "canonical_hash": canonical_hash,
            },
        ).one()
        event_type = "ticket_shadow_changed"
        event_id = uuid5(NAMESPACE_URL, f"coeus:{ticket_id}:{row.version}:{event_type}")
        connection.execute(
            text(
                """
                INSERT INTO coeus_outbox(
                  event_id, aggregate_id, aggregate_version, event_type, payload
                ) VALUES (
                  :event_id, CAST(:ticket_id AS uuid), :version, :event_type,
                  jsonb_build_object('ticket_id', :ticket_id, 'version', :version)
                )
                ON CONFLICT (aggregate_id, aggregate_version, event_type) DO NOTHING
                """
            ),
            {
                "event_id": event_id,
                "ticket_id": ticket_id,
                "version": row.version,
                "event_type": event_type,
            },
        )
    connection.execute(
        text(
            "DELETE FROM coeus_ticket_aggregates "
            "WHERE NOT (ticket_id = ANY(CAST(:ticket_ids AS uuid[])))"
        ),
        {"ticket_ids": ticket_ids},
    )


def _ensure_ticket_shadow_schema(connection: Any) -> None:
    connection.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS coeus_ticket_aggregates (
                ticket_id uuid PRIMARY KEY,
                version bigint NOT NULL CHECK (version > 0),
                payload jsonb NOT NULL,
                canonical_hash text NOT NULL,
                updated_at timestamptz NOT NULL DEFAULT now()
            )
            """
        )
    )
    connection.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS coeus_outbox (
                event_id uuid PRIMARY KEY,
                aggregate_id uuid NOT NULL,
                aggregate_version bigint NOT NULL,
                event_type text NOT NULL,
                payload jsonb NOT NULL,
                created_at timestamptz NOT NULL DEFAULT now(),
                delivered_at timestamptz,
                UNIQUE (aggregate_id, aggregate_version, event_type)
            )
            """
        )
    )
    connection.execute(
        text(
            "CREATE INDEX IF NOT EXISTS idx_coeus_outbox_pending "
            "ON coeus_outbox(created_at, event_id) WHERE delivered_at IS NULL"
        )
    )


def _validate_ticket_shadow(engine: Any, payload: dict[str, Any]) -> None:
    expected: dict[str, str] = {}
    tickets = payload.get("tickets", [])
    for ticket in tickets if isinstance(tickets, list) else []:
        try:
            ticket_id = ticket["fields"]["ticket_id"]["__uuid__"]
        except (KeyError, TypeError):
            continue
        canonical = json.dumps(ticket, sort_keys=True, separators=(",", ":"))
        expected[ticket_id] = sha256(canonical.encode("utf-8")).hexdigest()
    with engine.connect() as connection:
        actual = dict(
            connection.execute(
                text("SELECT ticket_id::text, canonical_hash FROM coeus_ticket_aggregates")
            ).all()
        )
    if actual != expected:
        raise RuntimeError("Ticket shadow reconciliation failed; relational cutover is unsafe.")
