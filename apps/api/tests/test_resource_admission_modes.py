from uuid import uuid4

import pytest

from coeus.core.errors import AppError
from coeus.domain.admission import AdmissionMode
from coeus.services.resource_admission import LocalResourceAdmissionController


def _controller(mode: AdmissionMode) -> LocalResourceAdmissionController:
    return LocalResourceAdmissionController(
        max_concurrent=2,
        max_concurrent_per_principal=1,
        max_units=2,
        mode=mode,
    )


def test_observe_mode_records_but_does_not_enforce_limits() -> None:
    controller = _controller(AdmissionMode.OBSERVE)
    principal = uuid4()

    with controller.reserve(principal), controller.reserve(principal), controller.reserve(uuid4()):
        assert controller.metrics_snapshot() == {
            "resource.admitted": 1,
            "resource.observed_denial": 2,
        }


def test_deployment_mode_enforces_shared_but_not_principal_limit() -> None:
    controller = _controller(AdmissionMode.DEPLOYMENT)
    principal = uuid4()

    with (
        controller.reserve(principal),
        controller.reserve(principal),
        pytest.raises(AppError, match="Resource capacity"),
        controller.reserve(uuid4()),
    ):
        pass

    assert controller.metrics_snapshot() == {
        "resource.admitted": 1,
        "resource.denied_deployment": 1,
        "resource.observed_denial": 1,
    }


def test_principal_mode_enforces_both_scopes_and_invalid_units() -> None:
    controller = _controller(AdmissionMode.PRINCIPAL)
    principal = uuid4()

    with (
        controller.reserve(principal),
        pytest.raises(AppError, match="Resource capacity"),
        controller.reserve(principal),
    ):
        pass
    with pytest.raises(AppError, match="Resource capacity"), controller.reserve(uuid4(), 0):
        pass

    assert controller.metrics_snapshot() == {
        "resource.admitted": 1,
        "resource.denied_invalid": 1,
        "resource.denied_principal": 1,
    }


def test_local_reservation_renewal_requires_an_active_context() -> None:
    reservation = _controller(AdmissionMode.PRINCIPAL).reserve(uuid4())

    with pytest.raises(RuntimeError, match="inactive"):
        reservation.renew()
    reservation.__enter__()
    reservation.renew()
    reservation.__exit__(None, None, None)
    reservation.__exit__(None, None, None)
