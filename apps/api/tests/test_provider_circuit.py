from datetime import UTC, datetime, timedelta

import pytest

from coeus.services.provider_circuit import ProviderCircuitBreaker


def _circuit(clock: list[datetime]) -> ProviderCircuitBreaker:
    return ProviderCircuitBreaker(
        failure_threshold=2,
        cooldown_seconds=30,
        clock=lambda: clock[0],
    )


def test_circuit_opens_rejects_and_allows_only_one_recovery_probe() -> None:
    clock = [datetime.now(UTC)]
    circuit = _circuit(clock)

    assert circuit.try_acquire()
    circuit.record_failure()
    assert circuit.try_acquire()
    circuit.record_failure()
    assert not circuit.can_attempt()
    assert not circuit.try_acquire()

    clock[0] += timedelta(seconds=30)
    assert circuit.can_attempt()
    assert circuit.try_acquire()
    assert not circuit.try_acquire()
    circuit.record_failure()
    assert not circuit.can_attempt()

    assert circuit.metrics_snapshot() == {
        "provider_circuit.failure": 1,
        "provider_circuit.opened": 2,
        "provider_circuit.probe": 1,
        "provider_circuit.rejected": 2,
    }


def test_success_closes_circuit_after_probe() -> None:
    clock = [datetime.now(UTC)]
    circuit = _circuit(clock)
    circuit.record_failure()
    circuit.record_failure()
    clock[0] += timedelta(seconds=30)
    assert circuit.try_acquire()

    circuit.record_success()

    assert circuit.can_attempt()
    assert circuit.try_acquire()


@pytest.mark.parametrize(
    ("threshold", "cooldown"),
    [(0, 1), (1, 0)],
)
def test_invalid_circuit_configuration_is_rejected(threshold: int, cooldown: int) -> None:
    with pytest.raises(ValueError, match="positive"):
        ProviderCircuitBreaker(
            failure_threshold=threshold,
            cooldown_seconds=cooldown,
        )
