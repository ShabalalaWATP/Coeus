import json
import os
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from threading import RLock
from typing import Any, Protocol

from sqlalchemy import text
from sqlalchemy.engine import Engine


@dataclass(frozen=True)
class StoredAuditPage:
    events: tuple[dict[str, object], ...]
    next_cursor: str | None


class AuditEventStore(Protocol):
    def append(self, event: dict[str, object]) -> None:
        pass

    def append_many(self, events: tuple[dict[str, object], ...]) -> None:
        pass

    def list_page(self, limit: int, before_event_id: str | None = None) -> StoredAuditPage:
        pass


class MemoryAuditEventStore:
    def __init__(self) -> None:
        self._events: list[dict[str, object]] = []
        self._lock = RLock()

    def append(self, event: dict[str, object]) -> None:
        with self._lock:
            self._events.append(deepcopy(event))

    def append_many(self, events: tuple[dict[str, object], ...]) -> None:
        with self._lock:
            self._events.extend(deepcopy(events))

    def list_page(self, limit: int, before_event_id: str | None = None) -> StoredAuditPage:
        with self._lock:
            return _page(tuple(deepcopy(self._events)), limit, before_event_id)


class FileAuditEventStore:
    def __init__(self, path: Path | str) -> None:
        self._path = Path(path)
        self._lock = RLock()

    def append(self, event: dict[str, object]) -> None:
        line = json.dumps(event, separators=(",", ":"), sort_keys=True)
        with self._lock:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._path.open("a", encoding="utf-8", newline="\n") as stream:
                stream.write(f"{line}\n")
                stream.flush()

    def append_many(self, events: tuple[dict[str, object], ...]) -> None:
        if not events:
            return
        with self._lock:
            existing = self._read()
            lines = tuple(
                json.dumps(event, separators=(",", ":"), sort_keys=True)
                for event in (*existing, *events)
            )
            self._path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self._path.with_suffix(f"{self._path.suffix}.tmp")
            try:
                temporary.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
                os.replace(temporary, self._path)
            finally:
                temporary.unlink(missing_ok=True)

    def list_page(self, limit: int, before_event_id: str | None = None) -> StoredAuditPage:
        with self._lock:
            return _page(self._read(), limit, before_event_id)

    def _read(self) -> tuple[dict[str, object], ...]:
        if not self._path.exists():
            return ()
        events: list[dict[str, object]] = []
        for line_number, line in enumerate(
            self._path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            try:
                event = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"Audit file {self._path} has invalid JSON on line {line_number}."
                ) from exc
            if not isinstance(event, dict):
                raise ValueError(
                    f"Audit file {self._path} line {line_number} must contain an object."
                )
            events.append(event)
        return tuple(events)


class PostgresAuditEventStore:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine
        self._schema_ready = False
        self._lock = RLock()

    def append(self, event: dict[str, object]) -> None:
        with self._lock, self._engine.begin() as connection:
            self._ensure_schema(connection)
            connection.execute(
                text(
                    """
                    INSERT INTO coeus_audit_events(
                        event_id, event_type, occurred_at, actor_user_id, metadata
                    ) VALUES (
                        CAST(:event_id AS uuid), :event_type, CAST(:occurred_at AS timestamptz),
                        :actor_user_id, CAST(:metadata AS jsonb)
                    )
                    """
                ),
                {
                    "event_id": event["event_id"],
                    "event_type": event["event_type"],
                    "occurred_at": event["occurred_at"],
                    "actor_user_id": event["actor_user_id"],
                    "metadata": json.dumps(event["metadata"]),
                },
            )

    def append_many(self, events: tuple[dict[str, object], ...]) -> None:
        if not events:
            return
        with self._lock, self._engine.begin() as connection:
            self._ensure_schema(connection)
            connection.execute(
                text(
                    """
                    INSERT INTO coeus_audit_events(
                        event_id, event_type, occurred_at, actor_user_id, metadata
                    ) VALUES (
                        CAST(:event_id AS uuid), :event_type, CAST(:occurred_at AS timestamptz),
                        :actor_user_id, CAST(:metadata AS jsonb)
                    )
                    """
                ),
                [_event_parameters(event) for event in events],
            )

    def list_page(self, limit: int, before_event_id: str | None = None) -> StoredAuditPage:
        with self._lock, self._engine.begin() as connection:
            self._ensure_schema(connection)
            rows = connection.execute(
                text(
                    """
                    SELECT event_id, event_type, occurred_at, actor_user_id, metadata
                    FROM coeus_audit_events
                    WHERE CAST(:before_event_id AS uuid) IS NULL
                       OR (occurred_at, event_id) < (
                           SELECT occurred_at, event_id
                           FROM coeus_audit_events
                           WHERE event_id = CAST(:before_event_id AS uuid)
                       )
                    ORDER BY occurred_at DESC, event_id DESC
                    LIMIT :fetch_limit
                    """
                ),
                {"before_event_id": before_event_id, "fetch_limit": limit + 1},
            ).mappings()
            newest_first = tuple(_row_payload(row) for row in rows)
        has_more = len(newest_first) > limit
        selected = newest_first[:limit]
        chronological = tuple(reversed(selected))
        cursor = str(selected[-1]["event_id"]) if has_more and selected else None
        return StoredAuditPage(chronological, cursor)

    def _ensure_schema(self, connection: Any) -> None:
        if self._schema_ready:
            return
        connection.execute(text(AUDIT_TABLE_SQL))
        connection.execute(text(AUDIT_ORDER_INDEX_SQL))
        self._schema_ready = True


AUDIT_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS coeus_audit_events (
    event_id uuid PRIMARY KEY,
    event_type text NOT NULL,
    occurred_at timestamptz NOT NULL,
    actor_user_id text,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb
)
"""

AUDIT_ORDER_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_coeus_audit_events_order
ON coeus_audit_events(occurred_at DESC, event_id DESC)
"""


def _page(
    events: tuple[dict[str, object], ...], limit: int, before_event_id: str | None
) -> StoredAuditPage:
    end = len(events)
    if before_event_id is not None:
        end = next(
            (
                index
                for index, event in enumerate(events)
                if str(event.get("event_id")) == before_event_id
            ),
            0,
        )
    start = max(0, end - limit)
    selected = events[start:end]
    cursor = str(selected[0]["event_id"]) if start > 0 and selected else None
    return StoredAuditPage(selected, cursor)


def _row_payload(row: Any) -> dict[str, object]:
    return {
        "event_id": str(row["event_id"]),
        "event_type": str(row["event_type"]),
        "occurred_at": row["occurred_at"].isoformat(),
        "actor_user_id": str(row["actor_user_id"]) if row["actor_user_id"] else None,
        "metadata": dict(row["metadata"]),
    }


def _event_parameters(event: dict[str, object]) -> dict[str, object]:
    return {
        "event_id": event["event_id"],
        "event_type": event["event_type"],
        "occurred_at": event["occurred_at"],
        "actor_user_id": event["actor_user_id"],
        "metadata": json.dumps(event["metadata"]),
    }
