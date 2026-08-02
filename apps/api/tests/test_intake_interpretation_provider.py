import json
from uuid import uuid4

import pytest

from coeus.core.config import Settings
from coeus.core.errors import AppError
from coeus.integrations.llm_gateway import LlmCall, LlmGeneration
from coeus.services.configurable_intake_provider import ConfigurableIntakeProvider
from coeus.services.intake_provider_execution import execute_intake_interpretation


def _valid_output() -> str:
    return json.dumps(
        {
            "target_field": "priority",
            "evidence": "not especially urgent",
            "normalised_value": "low",
            "time_period_start": None,
            "time_period_end": None,
            "abstain": False,
        }
    )


def _remote_settings(**updates: object) -> Settings:
    values: dict[str, object] = {
        "environment": "test",
        "llm_provider": "gemini_api",
        "gemini_api_key": "synthetic-key",
    }
    values.update(updates)
    return Settings(**values)


def test_mock_provider_does_not_prepare_remote_interpretation() -> None:
    provider = ConfigurableIntakeProvider(Settings(environment="test"), None)

    assert provider.prepare_intake_interpretation("unclear", "priority") is None


def test_oversized_answer_never_prepares_a_remote_call() -> None:
    provider = ConfigurableIntakeProvider(
        _remote_settings(),
        None,
        text_generator=lambda _call: pytest.fail("provider must not run"),
    )

    assert provider.prepare_intake_interpretation("x" * 4_097, "priority") is None


def test_valid_interpretation_freezes_structured_provider_call_and_usage() -> None:
    calls: list[LlmCall] = []

    def generate(call: LlmCall) -> str:
        calls.append(call)
        return LlmGeneration(_valid_output(), input_tokens=21, output_tokens=12)

    provider = ConfigurableIntakeProvider(_remote_settings(), None, text_generator=generate)
    prepared = provider.prepare_intake_interpretation("not especially urgent", "priority")

    assert prepared is not None and prepared.requires_admission
    outcome = prepared.execute()
    assert outcome.interpretation is not None
    assert outcome.interpretation.normalised_value == "low"
    assert outcome.provider_succeeded
    assert outcome.outcome == "provider_interpretation_confirmation_requested"
    assert outcome.validation_outcome == "passed"
    assert outcome.fallback_outcome == "not_used"
    assert outcome.input_tokens == 21
    assert outcome.output_tokens == 12
    assert outcome.input_hash and outcome.output_hash
    assert len(calls) == 1
    assert calls[0].structured_output
    assert calls[0].max_output_tokens == 192
    assert "not especially urgent" in calls[0].prompt
    assert "not especially urgent" not in calls[0].instructions


def test_invalid_output_falls_back_and_opens_shared_circuit() -> None:
    provider = ConfigurableIntakeProvider(
        _remote_settings(provider_circuit_failure_threshold=1),
        None,
        text_generator=lambda _call: "malformed",
    )
    prepared = provider.prepare_intake_interpretation("not especially urgent", "priority")
    assert prepared is not None

    outcome = prepared.execute()
    blocked = provider.prepare_intake_interpretation("not especially urgent", "priority")

    assert outcome.provider_succeeded
    assert outcome.interpretation is None
    assert outcome.outcome == "provider_interpretation_invalid_output"
    assert outcome.validation_outcome == "failed"
    assert outcome.error_class == "ProviderOutputValidationError"
    assert blocked is not None and not blocked.requires_admission
    assert blocked.execute().outcome == "provider_interpretation_circuit_open"


def test_valid_abstention_uses_fallback_without_opening_shared_circuit() -> None:
    output = json.loads(_valid_output())
    output.update(
        evidence="",
        normalised_value=None,
        abstain=True,
    )
    provider = ConfigurableIntakeProvider(
        _remote_settings(provider_circuit_failure_threshold=1),
        None,
        text_generator=lambda _call: json.dumps(output),
    )

    outcome = provider.prepare_intake_interpretation("banana", "priority")
    assert outcome is not None
    result = outcome.execute()
    following = provider.prepare_intake_interpretation("banana", "priority")

    assert result.outcome == "provider_interpretation_abstained"
    assert result.validation_outcome == "abstained"
    assert result.error_class is None
    assert following is not None and following.requires_admission


@pytest.mark.parametrize(
    ("error", "provider_succeeded", "validation"),
    (
        (
            AppError(502, "llm_provider_invalid_response", "Invalid response."),
            True,
            "failed",
        ),
        (
            AppError(503, "llm_provider_unavailable", "Unavailable."),
            False,
            "not_run",
        ),
        (RuntimeError("unexpected"), False, "not_run"),
    ),
)
def test_provider_failures_use_content_free_deterministic_fallback(
    error: Exception, provider_succeeded: bool, validation: str
) -> None:
    def fail(_call: LlmCall) -> str:
        raise error

    provider = ConfigurableIntakeProvider(_remote_settings(), None, text_generator=fail)
    prepared = provider.prepare_intake_interpretation("not especially urgent", "priority")
    assert prepared is not None

    outcome = prepared.execute()

    assert outcome.interpretation is None
    assert outcome.provider_succeeded is provider_succeeded
    assert outcome.validation_outcome == validation
    assert outcome.input_hash
    assert "not especially urgent" not in repr(outcome)


def test_missing_admission_never_executes_prepared_remote_call() -> None:
    calls = 0

    def generate(_call: LlmCall) -> str:
        nonlocal calls
        calls += 1
        return _valid_output()

    provider = ConfigurableIntakeProvider(_remote_settings(), None, text_generator=generate)

    outcome = execute_intake_interpretation(
        uuid4(), provider, None, "not especially urgent", "priority"
    )

    assert outcome is not None
    assert outcome.outcome == "provider_interpretation_admission_unavailable"
    assert outcome.error_class == "ProviderAdmissionUnavailable"
    assert calls == 0


def test_hosted_interpretation_egress_remains_disabled() -> None:
    calls = 0

    def generate(_call: LlmCall) -> str:
        nonlocal calls
        calls += 1
        return _valid_output()

    provider = ConfigurableIntakeProvider(
        _remote_settings(environment="dev"), None, text_generator=generate
    )

    assert provider.prepare_intake_interpretation("not especially urgent", "priority") is None
    assert calls == 0


def test_circuit_race_falls_back_without_calling_provider(monkeypatch) -> None:
    calls = 0

    def generate(_call: LlmCall) -> str:
        nonlocal calls
        calls += 1
        return _valid_output()

    provider = ConfigurableIntakeProvider(_remote_settings(), None, text_generator=generate)
    prepared = provider.prepare_intake_interpretation("not especially urgent", "priority")
    assert prepared is not None
    monkeypatch.setattr(provider._circuit, "try_acquire", lambda: False)

    outcome = prepared.execute()

    assert outcome.outcome == "provider_interpretation_circuit_open"
    assert calls == 0
