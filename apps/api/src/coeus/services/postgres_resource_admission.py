"""PostgreSQL leases for shared concurrent work and in-flight units."""

from types import TracebackType
from typing import Literal
from uuid import UUID, uuid4

from sqlalchemy import create_engine, text

from coeus.core.errors import AppError
from coeus.domain.admission import AdmissionMode, admission_denial_scope
from coeus.persistence.database_url import synchronous_database_url
from coeus.persistence.resource_lease_schema import RESOURCE_LEASE_SCHEMA_SQL
from coeus.services.admission_metrics import AdmissionMetrics


class PostgresResourceAdmissionController:
    def __init__(
        self,
        database_url: str,
        *,
        resource_type: str,
        max_concurrent: int,
        max_concurrent_per_principal: int,
        max_units: int,
        lease_seconds: int,
        mode: AdmissionMode = AdmissionMode.PRINCIPAL,
        metrics: AdmissionMetrics | None = None,
    ) -> None:
        self._engine = create_engine(synchronous_database_url(database_url), pool_pre_ping=True)
        self._resource_type = resource_type
        self._max_concurrent = max_concurrent
        self._max_concurrent_per_principal = max_concurrent_per_principal
        self._max_units = max_units
        self._lease_seconds = lease_seconds
        self._mode = mode
        self._metrics = metrics or AdmissionMetrics()
        with self._engine.begin() as connection:
            connection.execute(text(RESOURCE_LEASE_SCHEMA_SQL))

    def reserve(self, principal_id: UUID, units: int = 1) -> "PostgresResourceReservation":
        return PostgresResourceReservation(self, principal_id, units)

    def _acquire(self, principal_id: UUID, units: int) -> UUID:
        lease_id = uuid4()
        if units < 1:
            self._metrics.record(self._resource_type, "denied_invalid")
            raise AppError(429, "resource_capacity_exhausted", "Resource capacity is unavailable.")
        denial_scope: str | None = None
        observed_denial = False
        with self._engine.begin() as connection:
            connection.execute(
                text("SELECT pg_advisory_xact_lock(hashtext(:resource_type))"),
                {"resource_type": f"coeus:{self._resource_type}"},
            )
            connection.execute(text("DELETE FROM coeus_resource_leases WHERE expires_at <= now()"))
            counts = connection.execute(
                text(
                    """
                    SELECT count(*) AS active,
                           COALESCE(sum(units), 0) AS units,
                           count(*) FILTER (WHERE principal_id = :principal_id) AS principal_active
                    FROM coeus_resource_leases
                    WHERE resource_type = :resource_type
                    """
                ),
                {"principal_id": principal_id, "resource_type": self._resource_type},
            ).one()
            deployment_exceeded = (
                counts.active >= self._max_concurrent or counts.units + units > self._max_units
            )
            principal_exceeded = counts.principal_active >= self._max_concurrent_per_principal
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
                          :lease_id, :resource_type, :principal_id, :units,
                          now() + make_interval(secs => :lease_seconds)
                        )
                        """
                    ),
                    {
                        "lease_id": lease_id,
                        "resource_type": self._resource_type,
                        "principal_id": principal_id,
                        "units": units,
                        "lease_seconds": self._lease_seconds,
                    },
                )
        if denial_scope:
            self._metrics.record(self._resource_type, f"denied_{denial_scope}")
            raise AppError(429, "resource_capacity_exhausted", "Resource capacity is unavailable.")
        self._metrics.record(
            self._resource_type, "observed_denial" if observed_denial else "admitted"
        )
        return lease_id

    def _release(self, lease_id: UUID) -> None:
        with self._engine.begin() as connection:
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
                    SET expires_at = now() + make_interval(secs => :lease_seconds)
                    WHERE lease_id = :lease_id AND expires_at > now()
                    RETURNING lease_id
                    """
                ),
                {"lease_id": lease_id, "lease_seconds": self._lease_seconds},
            ).scalar_one_or_none()
        if renewed is None:
            self._metrics.record(self._resource_type, "renewal_failed")
            raise AppError(409, "resource_lease_expired", "Resource reservation has expired.")
        self._metrics.record(self._resource_type, "renewed")

    def metrics_snapshot(self) -> dict[str, int]:
        return self._metrics.snapshot()


class PostgresResourceReservation:
    def __init__(
        self, controller: PostgresResourceAdmissionController, principal_id: UUID, units: int
    ) -> None:
        self._controller = controller
        self._principal_id = principal_id
        self._units = units
        self._lease_id: UUID | None = None

    def __enter__(self) -> None:
        self._lease_id = self._controller._acquire(self._principal_id, self._units)

    def renew(self) -> None:
        if self._lease_id is None:
            raise RuntimeError("Cannot renew an inactive resource reservation.")
        self._controller._renew(self._lease_id)

    def __exit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc: BaseException | None,
        _traceback: TracebackType | None,
    ) -> Literal[False]:
        if self._lease_id is not None:
            self._controller._release(self._lease_id)
            self._lease_id = None
        return False
