from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text

from coeus.core.errors import AppError
from coeus.domain.admission import AdmissionMode
from coeus.services.postgres_resource_admission import PostgresResourceAdmissionController

pytestmark = pytest.mark.postgres


def _controller(database_url: str) -> PostgresResourceAdmissionController:
    return PostgresResourceAdmissionController(
        database_url,
        resource_type="test_resource",
        max_concurrent=2,
        max_concurrent_per_principal=1,
        max_units=3,
        lease_seconds=60,
    )


def test_two_instances_share_principal_concurrency_and_unit_limits(
    postgres_database_url: str,
) -> None:
    first = _controller(postgres_database_url)
    second = _controller(postgres_database_url)
    principal = uuid4()

    with first.reserve(principal, 2):
        with pytest.raises(AppError, match="Resource capacity"), second.reserve(principal):
            pass
        with (
            second.reserve(uuid4()),
            pytest.raises(AppError, match="Resource capacity"),
            first.reserve(uuid4()),
        ):
            pass


def test_expired_resource_lease_recovers_capacity(postgres_database_url: str) -> None:
    first = _controller(postgres_database_url)
    second = _controller(postgres_database_url)
    reservation = first.reserve(uuid4(), 3)
    reservation.__enter__()
    engine = create_engine(postgres_database_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE coeus_resource_leases SET expires_at = now() "
                "WHERE resource_type = 'test_resource'"
            )
        )

    with second.reserve(uuid4(), 3):
        pass
    reservation.__exit__(None, None, None)


def test_resource_lease_renewal_is_fenced_after_expiry(postgres_database_url: str) -> None:
    controller = _controller(postgres_database_url)
    reservation = controller.reserve(uuid4())
    reservation.__enter__()
    reservation.renew()
    assert controller.metrics_snapshot()["test_resource.renewed"] == 1

    engine = create_engine(postgres_database_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE coeus_resource_leases SET expires_at = now() "
                "WHERE resource_type = 'test_resource'"
            )
        )
    with pytest.raises(AppError, match="expired"):
        reservation.renew()
    assert controller.metrics_snapshot()["test_resource.renewal_failed"] == 1
    reservation.__exit__(None, None, None)


@pytest.mark.parametrize(
    ("mode", "principal_denied"),
    [
        (AdmissionMode.OBSERVE, False),
        (AdmissionMode.DEPLOYMENT, False),
        (AdmissionMode.PRINCIPAL, True),
    ],
)
def test_postgres_admission_modes_match_local_principal_policy(
    postgres_database_url: str,
    mode: AdmissionMode,
    principal_denied: bool,
) -> None:
    controller = PostgresResourceAdmissionController(
        postgres_database_url,
        resource_type=f"mode_{mode.value}",
        max_concurrent=2,
        max_concurrent_per_principal=1,
        max_units=2,
        lease_seconds=60,
        mode=mode,
    )
    principal = uuid4()
    with controller.reserve(principal):
        if principal_denied:
            with pytest.raises(AppError, match="Resource capacity"), controller.reserve(principal):
                pass
        else:
            with controller.reserve(principal):
                pass

    outcome = "denied_principal" if principal_denied else "observed_denial"
    assert controller.metrics_snapshot() == {
        f"mode_{mode.value}.admitted": 1,
        f"mode_{mode.value}.{outcome}": 1,
    }
