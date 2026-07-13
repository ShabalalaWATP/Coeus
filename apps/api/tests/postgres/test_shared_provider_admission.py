from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text

from coeus.core.errors import AppError
from coeus.services.postgres_provider_admission import PostgresProviderAdmissionController

pytestmark = pytest.mark.postgres


def _controller(database_url: str, *, calls: int = 2) -> PostgresProviderAdmissionController:
    return PostgresProviderAdmissionController(
        database_url,
        max_concurrent=1,
        max_calls_per_window=calls,
        max_calls_per_principal=1,
        window_seconds=60,
    )


def test_two_instances_share_concurrency_and_principal_limits(
    postgres_database_url: str,
) -> None:
    first = _controller(postgres_database_url)
    second = _controller(postgres_database_url)
    principal = uuid4()

    with (
        first.reserve(principal),
        pytest.raises(AppError, match="Provider capacity"),
        second.reserve(uuid4()),
    ):
        pass

    with first.reserve(principal) as reservation:
        reservation.commit()
    with pytest.raises(AppError, match="Provider capacity"), second.reserve(principal):
        pass
    with second.reserve(uuid4()) as reservation:
        reservation.commit()


def test_refund_and_expiry_release_capacity_across_instances(
    postgres_database_url: str,
) -> None:
    first = _controller(postgres_database_url, calls=1)
    second = _controller(postgres_database_url, calls=1)
    with pytest.raises(RuntimeError, match="provider failed"), first.reserve(uuid4()):
        raise RuntimeError("provider failed")
    with first.reserve(uuid4()) as reservation:
        reservation.commit()

    engine = create_engine(postgres_database_url)
    with engine.begin() as connection:
        connection.execute(text("UPDATE coeus_resource_leases SET expires_at = now()"))

    with second.reserve(uuid4()) as reservation:
        reservation.commit()
