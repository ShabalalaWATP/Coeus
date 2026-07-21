"""PostgreSQL outbox adapter with fenced, skip-locked claims."""

from typing import Any
from uuid import UUID

from sqlalchemy import create_engine, text

from coeus.domain.outbox import (
    FailureDisposition,
    OutboxClaimLost,
    OutboxEventNotFound,
    OutboxMessage,
    OutboxStatus,
    ReplayDisposition,
)
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
    ) -> FailureDisposition:
        if retry_seconds < 1 or max_attempts < 1:
            raise ValueError("Outbox retry duration and maximum attempts must be positive.")
        dead_lettered = self._settle(
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
            RETURNING dead_lettered_at IS NOT NULL
            """,
            {
                "error": error[:1000],
                "retry_seconds": retry_seconds,
                "max_attempts": max_attempts,
            },
        )
        return (
            FailureDisposition.DEAD_LETTERED
            if dead_lettered is True
            else FailureDisposition.RETRY_SCHEDULED
        )

    def status(self) -> OutboxStatus:
        with self._engine.connect() as connection:
            pending = (
                connection.execute(
                    text(
                        """
                    SELECT
                      count(*) AS pending_count,
                      count(*) FILTER (
                        WHERE attempt_count > 1 OR last_error IS NOT NULL
                      ) AS retrying_count,
                      EXTRACT(EPOCH FROM (now() - min(created_at)))
                        AS oldest_pending_age_seconds
                    FROM coeus_outbox
                    WHERE delivered_at IS NULL AND dead_lettered_at IS NULL
                    """
                    )
                )
                .mappings()
                .one()
            )
            dead_letter_count = connection.execute(
                text(
                    """
                    SELECT count(*) FROM coeus_outbox
                    WHERE delivered_at IS NULL AND dead_lettered_at IS NOT NULL
                    """
                )
            ).scalar_one()
        age = pending["oldest_pending_age_seconds"]
        return OutboxStatus(
            pending_count=pending["pending_count"],
            retrying_count=pending["retrying_count"],
            dead_letter_count=dead_letter_count,
            oldest_pending_age_seconds=max(0, int(age)) if age is not None else None,
        )

    def replay_dead_letter(self, event_id: UUID) -> ReplayDisposition:
        with self._engine.begin() as connection:
            replayed = connection.execute(
                text(
                    """
                    UPDATE coeus_outbox SET
                      available_at = now(),
                      attempt_count = 0,
                      claimed_by = NULL,
                      claim_expires_at = NULL,
                      last_error = NULL,
                      dead_lettered_at = NULL
                    WHERE event_id = :event_id
                      AND delivered_at IS NULL
                      AND dead_lettered_at IS NOT NULL
                    RETURNING event_id
                    """
                ),
                {"event_id": event_id},
            ).scalar_one_or_none()
            if replayed is not None:
                return ReplayDisposition.REPLAYED
            state = connection.execute(
                text(
                    """
                    SELECT delivered_at IS NOT NULL AS delivered
                    FROM coeus_outbox WHERE event_id = :event_id
                    """
                ),
                {"event_id": event_id},
            ).scalar_one_or_none()
        if state is None:
            raise OutboxEventNotFound(f"Outbox event {event_id} does not exist.")
        return (
            ReplayDisposition.ALREADY_DELIVERED
            if state is True
            else ReplayDisposition.ALREADY_PENDING
        )

    def _settle(
        self,
        event_id: UUID,
        worker_id: UUID,
        statement: str,
        parameters: dict[str, object] | None = None,
    ) -> object:
        values = {"event_id": event_id, "worker_id": worker_id, **(parameters or {})}
        with self._engine.begin() as connection:
            settled = connection.execute(text(statement), values).scalar_one_or_none()
        if settled is None:
            raise OutboxClaimLost(f"Outbox claim for {event_id} is no longer owned by this worker.")
        return settled


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
