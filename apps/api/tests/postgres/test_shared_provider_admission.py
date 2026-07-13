from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text

from coeus.core.errors import AppError
from coeus.domain.admission import AdmissionMode
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


def test_provider_lease_renewal_is_fenced_after_expiry(postgres_database_url: str) -> None:
    controller = _controller(postgres_database_url)
    reservation = controller.reserve(uuid4())
    reservation.__enter__()
    reservation.renew()
    engine = create_engine(postgres_database_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE coeus_resource_leases SET expires_at = now() "
                "WHERE resource_type = 'provider'"
            )
        )
    with pytest.raises(AppError, match="expired"):
        reservation.renew()
    reservation.__exit__(None, None, None)


@pytest.mark.parametrize(
    ("mode", "denied"),
    [
        (AdmissionMode.OBSERVE, False),
        (AdmissionMode.DEPLOYMENT, False),
        (AdmissionMode.PRINCIPAL, True),
    ],
)
def test_postgres_provider_modes_stage_principal_enforcement(
    postgres_database_url: str, mode: AdmissionMode, denied: bool
) -> None:
    controller = PostgresProviderAdmissionController(
        postgres_database_url,
        max_concurrent=2,
        max_calls_per_window=10,
        max_calls_per_principal=1,
        window_seconds=60,
        mode=mode,
    )
    principal = uuid4()
    with controller.reserve(principal):
        if denied:
            with pytest.raises(AppError), controller.reserve(principal):
                pass
        else:
            with controller.reserve(principal):
                pass
