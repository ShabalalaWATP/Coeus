from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from coeus.core.errors import AppError
from coeus.domain.admission import AdmissionMode
from coeus.services.provider_admission import ProviderAdmissionController


def _controller(clock: list[datetime]) -> ProviderAdmissionController:
    return ProviderAdmissionController(
        max_concurrent=1,
        max_calls_per_window=2,
        max_calls_per_principal=1,
        window_seconds=60,
        clock=lambda: clock[0],
    )


def test_provider_admission_enforces_principal_and_deployment_windows() -> None:
    clock = [datetime.now(UTC)]
    controller = _controller(clock)
    first = uuid4()
    second = uuid4()
    with controller.reserve(first) as reservation:
        reservation.commit()

    with pytest.raises(AppError, match="Provider capacity"), controller.reserve(first):
        pass

    with controller.reserve(second) as reservation:
        reservation.commit()
    with pytest.raises(AppError, match="Provider capacity"), controller.reserve(uuid4()):
        pass


def test_provider_admission_refunds_failures_and_recovers_after_window() -> None:
    clock = [datetime.now(UTC)]
    controller = _controller(clock)
    principal = uuid4()
    with pytest.raises(RuntimeError, match="provider failed"), controller.reserve(principal):
        raise RuntimeError("provider failed")

    with controller.reserve(principal) as reservation:
        reservation.commit()
    clock[0] += timedelta(seconds=61)
    with controller.reserve(principal) as reservation:
        reservation.commit()


def test_provider_admission_rejects_concurrent_acquisition() -> None:
    clock = [datetime.now(UTC)]
    controller = _controller(clock)
    with (
        controller.reserve(uuid4()),
        pytest.raises(AppError, match="Provider capacity"),
        controller.reserve(uuid4()),
    ):
        pass


@pytest.mark.parametrize(
    ("mode", "denied"),
    [
        (AdmissionMode.OBSERVE, False),
        (AdmissionMode.DEPLOYMENT, False),
        (AdmissionMode.PRINCIPAL, True),
    ],
)
def test_provider_modes_stage_principal_enforcement(mode: AdmissionMode, denied: bool) -> None:
    controller = ProviderAdmissionController(
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
    outcome = "denied_principal" if denied else "observed_denial"
    assert controller.metrics_snapshot() == {
        "provider.admitted": 1,
        f"provider.{outcome}": 1,
    }


def test_provider_reservation_renewal_requires_active_context() -> None:
    clock = [datetime.now(UTC)]
    reservation = _controller(clock).reserve(uuid4())
    with pytest.raises(RuntimeError, match="inactive"):
        reservation.renew()
    reservation.__enter__()
    reservation.renew()
    reservation.__exit__(None, None, None)
    reservation.__exit__(None, None, None)
