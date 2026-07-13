"""PostgreSQL-backed provider reservations shared across API processes."""

from types import TracebackType
from typing import Literal
from uuid import UUID, uuid4

from sqlalchemy import create_engine, text

from coeus.core.errors import AppError
from coeus.domain.admission import AdmissionMode, admission_denial_scope
from coeus.persistence.database_url import synchronous_database_url
from coeus.persistence.resource_lease_schema import RESOURCE_LEASE_SCHEMA_SQL
from coeus.services.admission_metrics import AdmissionMetrics


class PostgresProviderAdmissionController:
    def __init__(
        self,
        database_url: str,
        *,
        max_concurrent: int,
        max_calls_per_window: int,
        max_calls_per_principal: int,
        window_seconds: int,
        mode: AdmissionMode = AdmissionMode.PRINCIPAL,
        metrics: AdmissionMetrics | None = None,
    ) -> None:
        self._engine = create_engine(synchronous_database_url(database_url), pool_pre_ping=True)
        self._max_concurrent = max_concurrent
        self._max_calls_per_window = max_calls_per_window
        self._max_calls_per_principal = max_calls_per_principal
        self._window_seconds = window_seconds
        self._mode = mode
        self._metrics = metrics or AdmissionMetrics()
        with self._engine.begin() as connection:
            connection.execute(text(RESOURCE_LEASE_SCHEMA_SQL))

    def reserve(self, principal_id: UUID) -> "PostgresProviderReservation":
        return PostgresProviderReservation(self, principal_id)

    def _acquire(self, principal_id: UUID) -> UUID:
        lease_id = uuid4()
        denial_scope: str | None = None
        observed_denial = False
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
            deployment_exceeded = (
                counts.active >= self._max_concurrent
                or counts.deployment_calls >= self._max_calls_per_window
            )
            principal_exceeded = counts.principal_calls >= self._max_calls_per_principal
            denial_scope = admission_denial_scope(
                self._mode,
                deployment_exceeded=deployment_exceeded,
                principal_exceeded=principal_exceeded,
            )
            observed_denial = deployment_exceeded or principal_exceeded
            if denial_scope is None:
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
        if denial_scope:
            self._metrics.record("provider", f"denied_{denial_scope}")
            raise AppError(
                429,
                "provider_capacity_exhausted",
                "Provider capacity is temporarily unavailable.",
            )
        self._metrics.record("provider", "observed_denial" if observed_denial else "admitted")
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

    def _renew(self, lease_id: UUID) -> None:
        with self._engine.begin() as connection:
            renewed = connection.execute(
                text(
                    """
                    UPDATE coeus_resource_leases
                    SET expires_at = now() + make_interval(secs => :window_seconds)
                    WHERE lease_id = :lease_id AND expires_at > now()
                      AND released_at IS NULL
                    RETURNING lease_id
                    """
                ),
                {"lease_id": lease_id, "window_seconds": self._window_seconds},
            ).scalar_one_or_none()
        if renewed is None:
            self._metrics.record("provider", "renewal_failed")
            raise AppError(409, "provider_lease_expired", "Provider reservation has expired.")
        self._metrics.record("provider", "renewed")

    def metrics_snapshot(self) -> dict[str, int]:
        return self._metrics.snapshot()


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

    def renew(self) -> None:
        if self._lease_id is None:
            raise RuntimeError("Cannot renew an inactive provider reservation.")
        self._controller._renew(self._lease_id)

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
