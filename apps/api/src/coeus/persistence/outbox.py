"""PostgreSQL outbox adapter with fenced, skip-locked claims."""

from typing import Any
from uuid import UUID

from sqlalchemy import create_engine, text

from coeus.domain.outbox import OutboxClaimLost, OutboxMessage
from coeus.persistence.database_url import synchronous_database_url


class PostgresOutboxStore:
    def __init__(self, database_url: str) -> None:
        self._engine = create_engine(synchronous_database_url(database_url), pool_pre_ping=True)

    def claim_pending(
        self, worker_id: UUID, *, limit: int, lease_seconds: int
    ) -> tuple[OutboxMessage, ...]:
        if limit < 1 or lease_seconds < 1:
            raise ValueError("Outbox claim limit and lease duration must be positive.")
        with self._engine.begin() as connection:
            rows = connection.execute(
                text(
                    """
                    WITH candidates AS (
                      SELECT event_id FROM coeus_outbox
                      WHERE delivered_at IS NULL
                        AND dead_lettered_at IS NULL
                        AND available_at <= now()
                        AND (claimed_by IS NULL OR claim_expires_at <= now())
                      ORDER BY created_at, event_id
                      LIMIT :limit
                      FOR UPDATE SKIP LOCKED
                    )
                    UPDATE coeus_outbox AS event SET
                      claimed_by = :worker_id,
                      claim_expires_at = now() + make_interval(secs => :lease_seconds),
                      attempt_count = event.attempt_count + 1
                    FROM candidates
                    WHERE event.event_id = candidates.event_id
                    RETURNING event.event_id, event.aggregate_id, event.aggregate_version,
                              event.event_type, event.payload, event.created_at,
                              event.attempt_count
                    """
                ),
                {"worker_id": worker_id, "limit": limit, "lease_seconds": lease_seconds},
            ).mappings()
            return tuple(_message(row) for row in rows)

    def mark_delivered(self, event_id: UUID, worker_id: UUID) -> None:
        self._settle(
            event_id,
            worker_id,
            """
            UPDATE coeus_outbox SET delivered_at = now(), claimed_by = NULL,
              claim_expires_at = NULL, last_error = NULL
            WHERE event_id = :event_id AND claimed_by = :worker_id
              AND claim_expires_at > now()
              AND delivered_at IS NULL AND dead_lettered_at IS NULL
            RETURNING event_id
            """,
        )

    def mark_failed(
        self,
        event_id: UUID,
        worker_id: UUID,
        error: str,
        *,
        retry_seconds: int,
        max_attempts: int,
    ) -> None:
        if retry_seconds < 1 or max_attempts < 1:
            raise ValueError("Outbox retry duration and maximum attempts must be positive.")
        self._settle(
            event_id,
            worker_id,
            """
            UPDATE coeus_outbox SET
              claimed_by = NULL,
              claim_expires_at = NULL,
              last_error = :error,
              available_at = now() + make_interval(secs => :retry_seconds),
              dead_lettered_at = CASE WHEN attempt_count >= :max_attempts THEN now()
                                      ELSE dead_lettered_at END
            WHERE event_id = :event_id AND claimed_by = :worker_id
              AND claim_expires_at > now()
              AND delivered_at IS NULL AND dead_lettered_at IS NULL
            RETURNING event_id
            """,
            {
                "error": error[:1000],
                "retry_seconds": retry_seconds,
                "max_attempts": max_attempts,
            },
        )

    def _settle(
        self,
        event_id: UUID,
        worker_id: UUID,
        statement: str,
        parameters: dict[str, object] | None = None,
    ) -> None:
        values = {"event_id": event_id, "worker_id": worker_id, **(parameters or {})}
        with self._engine.begin() as connection:
            settled = connection.execute(text(statement), values).scalar_one_or_none()
        if settled is None:
            raise OutboxClaimLost(f"Outbox claim for {event_id} is no longer owned by this worker.")


def _message(row: Any) -> OutboxMessage:
    return OutboxMessage(
        event_id=row["event_id"],
        aggregate_id=row["aggregate_id"],
        aggregate_version=row["aggregate_version"],
        event_type=row["event_type"],
        payload=dict(row["payload"]),
        created_at=row["created_at"],
        attempt_count=row["attempt_count"],
    )
