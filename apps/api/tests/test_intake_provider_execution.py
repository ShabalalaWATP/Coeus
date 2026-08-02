from uuid import uuid4

import pytest

from coeus.core.config import Settings
from coeus.core.errors import AppError
from coeus.domain.tickets import IntakeDetails
from coeus.services.configurable_intake_provider import ConfigurableIntakeProvider
from coeus.services.intake import MockLlmProvider
from coeus.services.intake_provider_execution import (
    execute_intake_interpretation,
    execute_intake_reply,
)
from coeus.services.provider_admission import ProviderAdmissionController


def _admission() -> ProviderAdmissionController:
    return ProviderAdmissionController(
        max_concurrent=1,
        max_calls_per_window=3,
        max_calls_per_principal=3,
        window_seconds=60,
    )


def _remote(generator):  # type: ignore[no-untyped-def]
    return ConfigurableIntakeProvider(
        Settings(
            environment="test",
            llm_provider="gemini_api",
            gemini_api_key="synthetic-key",
            provider_circuit_failure_threshold=1,
        ),
        None,
        text_generator=generator,
    )


def test_interpretation_returns_none_for_provider_without_prepare_method() -> None:
    assert (
        execute_intake_interpretation(
            uuid4(),
            MockLlmProvider(),
            None,
            "banana",
            "priority",
        )
        is None
    )


def test_shared_circuit_fallback_executes_without_new_admission() -> None:
    actor_id = uuid4()
    provider = _remote(lambda _call: "malformed")
    first = execute_intake_interpretation(
        actor_id,
        provider,
        _admission(),
        "banana",
        "priority",
    )
    second = execute_intake_interpretation(
        actor_id,
        provider,
        _admission(),
        "banana",
        "priority",
    )

    assert first is not None and first.validation_outcome == "failed"
    assert second is not None
    assert second.outcome == "provider_interpretation_circuit_open"


def test_provider_error_refunds_interpretation_reservation() -> None:
    actor_id = uuid4()

    def fail(_call):  # type: ignore[no-untyped-def]
        raise RuntimeError("synthetic failure")

    admission = _admission()
    outcome = execute_intake_interpretation(
        actor_id,
        _remote(fail),
        admission,
        "banana",
        "priority",
    )

    assert outcome is not None and not outcome.provider_succeeded
    assert admission.metrics_snapshot() == {"provider.admitted": 1}


def test_non_capacity_admission_error_is_not_hidden() -> None:
    class BrokenAdmission:
        def reserve(self, _principal_id):  # type: ignore[no-untyped-def]
            raise AppError(503, "admission_store_failed", "Synthetic failure.")

    with pytest.raises(AppError, match="Synthetic failure"):
        execute_intake_interpretation(
            uuid4(),
            _remote(lambda _call: "{}"),
            BrokenAdmission(),  # type: ignore[arg-type]
            "banana",
            "priority",
        )


def test_non_preparable_reply_provider_is_rejected_when_admission_is_enabled() -> None:
    with pytest.raises(RuntimeError, match="immutable intake reply"):
        execute_intake_reply(
            uuid4(),
            MockLlmProvider(),
            _admission(),
            IntakeDetails(missing_information=("priority",)),
            (),
        )
