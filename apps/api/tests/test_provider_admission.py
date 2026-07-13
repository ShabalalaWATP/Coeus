from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from coeus.core.errors import AppError
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
