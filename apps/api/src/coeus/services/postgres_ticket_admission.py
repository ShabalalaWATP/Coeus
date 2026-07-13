"""Cross-process retained-ticket admission and reference allocation."""

from types import TracebackType
from typing import Literal
from uuid import UUID, uuid4

from sqlalchemy import create_engine, text

from coeus.core.errors import AppError
from coeus.persistence.database_url import synchronous_database_url
from coeus.services.postgres_provider_admission import RESOURCE_LEASE_SCHEMA_SQL


class PostgresTicketAdmissionController:
    def __init__(
        self,
        database_url: str,
        *,
        max_retained: int,
        max_retained_per_principal: int,
        lease_seconds: int = 60,
    ) -> None:
        self._engine = create_engine(synchronous_database_url(database_url), pool_pre_ping=True)
        self._max_retained = max_retained
        self._max_retained_per_principal = max_retained_per_principal
        self._lease_seconds = lease_seconds
        with self._engine.begin() as connection:
            connection.execute(text(RESOURCE_LEASE_SCHEMA_SQL))

    def reserve(self, principal_id: UUID) -> "PostgresTicketReservation":
        return PostgresTicketReservation(self, principal_id)

    def _acquire(self, principal_id: UUID) -> tuple[UUID, str]:
        lease_id = uuid4()
        denied = False
        reference = ""
        with self._engine.begin() as connection:
            connection.execute(text("SELECT pg_advisory_xact_lock(hashtext('coeus:tickets'))"))
            connection.execute(text("DELETE FROM coeus_resource_leases WHERE expires_at <= now()"))
            retained = connection.execute(
                text(
                    """
                    SELECT
                      count(*) FILTER (WHERE consumes_capacity) AS deployment_count,
                      count(*) FILTER (
                        WHERE consumes_capacity AND requester_user_id = :principal_id
                      ) AS principal_count
                    FROM coeus_ticket_aggregates
                    """
                ),
                {"principal_id": principal_id},
            ).one()
            pending = connection.execute(
                text(
                    """
                    SELECT count(*) AS deployment_count,
                           count(*) FILTER (WHERE principal_id = :principal_id) AS principal_count
                    FROM coeus_resource_leases
                    WHERE resource_type = 'ticket_creation'
                    """
                ),
                {"principal_id": principal_id},
            ).one()
            if (
                retained.deployment_count + pending.deployment_count >= self._max_retained
                or retained.principal_count + pending.principal_count
                >= self._max_retained_per_principal
            ):
                denied = True
            else:
                counter = connection.execute(
                    text(
                        """
                        INSERT INTO coeus_state(namespace, payload, updated_at)
                        VALUES ('ticket_meta', '{"counter": 1}'::jsonb, now())
                        ON CONFLICT (namespace) DO UPDATE SET
                          payload = jsonb_build_object(
                            'counter', COALESCE((coeus_state.payload ->> 'counter')::bigint, 0) + 1
                          ),
                          updated_at = now()
                        RETURNING (payload ->> 'counter')::bigint
                        """
                    )
                ).scalar_one()
                reference = f"TCK-{counter:04d}"
                connection.execute(
                    text(
                        """
                        INSERT INTO coeus_resource_leases(
                          lease_id, resource_type, principal_id, units, expires_at
                        ) VALUES (
                          :lease_id, 'ticket_creation', :principal_id, 1,
                          now() + make_interval(secs => :lease_seconds)
                        )
                        """
                    ),
                    {
                        "lease_id": lease_id,
                        "principal_id": principal_id,
                        "lease_seconds": self._lease_seconds,
                    },
                )
        if denied:
            raise AppError(429, "ticket_capacity_exhausted", "Ticket capacity is unavailable.")
        return lease_id, reference

    def _release(self, lease_id: UUID) -> None:
        with self._engine.begin() as connection:
            connection.execute(
                text("DELETE FROM coeus_resource_leases WHERE lease_id = :lease_id"),
                {"lease_id": lease_id},
            )


class PostgresTicketReservation:
    def __init__(self, controller: PostgresTicketAdmissionController, principal_id: UUID) -> None:
        self._controller = controller
        self._principal_id = principal_id
        self._lease_id: UUID | None = None

    def __enter__(self) -> str:
        self._lease_id, reference = self._controller._acquire(self._principal_id)
        return reference

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
