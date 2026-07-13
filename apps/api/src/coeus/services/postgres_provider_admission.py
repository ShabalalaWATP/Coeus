"""PostgreSQL-backed provider reservations shared across API processes."""

from types import TracebackType
from typing import Literal
from uuid import UUID, uuid4

from sqlalchemy import create_engine, text

from coeus.core.errors import AppError
from coeus.persistence.state_store import _sync_database_url

RESOURCE_LEASE_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS coeus_resource_leases (
    lease_id uuid PRIMARY KEY,
    resource_type text NOT NULL,
    principal_id uuid NOT NULL,
    units bigint NOT NULL CHECK (units > 0),
    acquired_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz NOT NULL,
    committed boolean NOT NULL DEFAULT false,
    released_at timestamptz
)
"""


class PostgresProviderAdmissionController:
    def __init__(
        self,
        database_url: str,
        *,
        max_concurrent: int,
        max_calls_per_window: int,
        max_calls_per_principal: int,
        window_seconds: int,
    ) -> None:
        self._engine = create_engine(_sync_database_url(database_url), pool_pre_ping=True)
        self._max_concurrent = max_concurrent
        self._max_calls_per_window = max_calls_per_window
        self._max_calls_per_principal = max_calls_per_principal
        self._window_seconds = window_seconds
        with self._engine.begin() as connection:
            connection.execute(text(RESOURCE_LEASE_SCHEMA_SQL))

    def reserve(self, principal_id: UUID) -> "PostgresProviderReservation":
        return PostgresProviderReservation(self, principal_id)

    def _acquire(self, principal_id: UUID) -> UUID:
        lease_id = uuid4()
        denied = False
        with self._engine.begin() as connection:
            connection.execute(text("SELECT pg_advisory_xact_lock(hashtext('coeus:provider'))"))
            connection.execute(text("DELETE FROM coeus_resource_leases WHERE expires_at <= now()"))
            counts = connection.execute(
                text(
                    """
                    SELECT
                      count(*) FILTER (WHERE released_at IS NULL) AS active,
                      count(*) AS deployment_calls,
                      count(*) FILTER (WHERE principal_id = :principal_id) AS principal_calls
                    FROM coeus_resource_leases
                    WHERE resource_type = 'provider'
                    """
                ),
                {"principal_id": principal_id},
            ).one()
            if (
                counts.active >= self._max_concurrent
                or counts.deployment_calls >= self._max_calls_per_window
                or counts.principal_calls >= self._max_calls_per_principal
            ):
                denied = True
            else:
                connection.execute(
                    text(
                        """
                        INSERT INTO coeus_resource_leases(
                          lease_id, resource_type, principal_id, units, expires_at
                        ) VALUES (
                          :lease_id, 'provider', :principal_id, 1,
                          now() + make_interval(secs => :window_seconds)
                        )
                        """
                    ),
                    {
                        "lease_id": lease_id,
                        "principal_id": principal_id,
                        "window_seconds": self._window_seconds,
                    },
                )
        if denied:
            raise AppError(
                429,
                "provider_capacity_exhausted",
                "Provider capacity is temporarily unavailable.",
            )
        return lease_id

    def _release(self, lease_id: UUID, *, committed: bool) -> None:
        with self._engine.begin() as connection:
            if committed:
                connection.execute(
                    text(
                        "UPDATE coeus_resource_leases "
                        "SET committed = true, released_at = now() "
                        "WHERE lease_id = :lease_id AND released_at IS NULL"
                    ),
                    {"lease_id": lease_id},
                )
            else:
                connection.execute(
                    text("DELETE FROM coeus_resource_leases WHERE lease_id = :lease_id"),
                    {"lease_id": lease_id},
                )


class PostgresProviderReservation:
    def __init__(self, controller: PostgresProviderAdmissionController, principal_id: UUID) -> None:
        self._controller = controller
        self._principal_id = principal_id
        self._lease_id: UUID | None = None
        self._committed = False

    def __enter__(self) -> "PostgresProviderReservation":
        self._lease_id = self._controller._acquire(self._principal_id)
        return self

    def commit(self) -> None:
        self._committed = True

    def __exit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc: BaseException | None,
        _traceback: TracebackType | None,
    ) -> Literal[False]:
        if self._lease_id is not None:
            self._controller._release(self._lease_id, committed=self._committed)
            self._lease_id = None
        return False
