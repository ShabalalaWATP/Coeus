from collections.abc import Callable
from uuid import UUID, uuid4

import pytest

from coeus.core.config import Settings
from coeus.core.errors import AppError
from coeus.domain.advisory_agents import (
    AdviceItemKind,
    AdvisoryAgentKind,
    AdvisoryPrompt,
    AgentAdvice,
    AgentAdviceItem,
)
from coeus.integrations.llm_gateway import LlmCall, LlmGeneration
from coeus.services.bounded_advisory import BoundedAdvisoryService


class RecordingReservation:
    def __init__(self, on_enter: Callable[[], None] | None = None) -> None:
        self.committed = False
        self._on_enter = on_enter

    def __enter__(self) -> "RecordingReservation":
        if self._on_enter:
            self._on_enter()
        return self

    def commit(self) -> None:
        self.committed = True

    def renew(self) -> None:
        return None

    def __exit__(self, *_args: object) -> None:
        return None


class RecordingAdmission:
    def __init__(
        self,
        *,
        on_enter: Callable[[], None] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.principals: list[UUID] = []
        self.reservations: list[RecordingReservation] = []
        self._on_enter = on_enter
        self._error = error

    def reserve(self, principal_id: UUID) -> RecordingReservation:
        self.principals.append(principal_id)
        if self._error:
            raise self._error
        reservation = RecordingReservation(self._on_enter)
        self.reservations.append(reservation)
        return reservation


def _prompt() -> AdvisoryPrompt:
    return AdvisoryPrompt(
        data='{"title":"Synthetic harbour brief"}',
        instructions="Return only bounded JSON suggestions.",
        prompt_version="search-planner-v1",
        policy_version="advisory-policy-v1",
        context_schema_version="search-context-v1",
        max_output_tokens=192,
    )


def _fallback() -> tuple[AgentAdviceItem, ...]:
    return (
        AgentAdviceItem(
            AdviceItemKind.QUERY_EXPANSION,
            "baseline_query",
            "synthetic harbour brief",
            ("title",),
        ),
    )


def _parsed(_raw: str) -> tuple[AgentAdviceItem, ...]:
    return (
        AgentAdviceItem(
            AdviceItemKind.ENTITY,
            "place_entity",
            "North Harbour",
            ("area_or_region",),
        ),
    )


def _service(
    settings: Settings,
    admission: RecordingAdmission,
    generator: Callable[[LlmCall], str],
) -> BoundedAdvisoryService:
    return BoundedAdvisoryService(settings, None, admission, text_generator=generator)


def test_advice_contract_rejects_cross_agent_items_and_unbounded_values() -> None:
    provenance = (
        _service(
            Settings(environment="test"),
            RecordingAdmission(),
            lambda _call: pytest.fail("mock must remain local"),
        )
        .advise(
            agent=AdvisoryAgentKind.SEARCH_PLANNER,
            requester_id=uuid4(),
            prompt=_prompt(),
            fallback_items=_fallback(),
            parser=_parsed,
        )
        .provenance
    )

    with pytest.raises(ValueError, match="not permitted"):
        AgentAdvice(
            AdvisoryAgentKind.INTAKE_PLANNER,
            _fallback(),
            provenance,
        )
    with pytest.raises(ValueError, match="identifiers"):
        AgentAdviceItem(AdviceItemKind.AMBIGUITY, "Not valid", "Detail")
    with pytest.raises(ValueError, match="printable"):
        AgentAdviceItem(AdviceItemKind.AMBIGUITY, "valid", "Line one\nLine two")
    with pytest.raises(ValueError, match="token limit"):
        AdvisoryPrompt("{}", "JSON", "v1", "v1", "v1", max_output_tokens=513)


def test_mock_provider_returns_deterministic_advice_without_admission() -> None:
    admission = RecordingAdmission()
    advice = _service(
        Settings(environment="test"),
        admission,
        lambda _call: pytest.fail("mock must remain local"),
    ).advise(
        agent=AdvisoryAgentKind.SEARCH_PLANNER,
        requester_id=uuid4(),
        prompt=_prompt(),
        fallback_items=_fallback(),
        parser=_parsed,
    )

    assert advice.items == _fallback()
    assert advice.provenance.outcome == "local_provider"
    assert advice.provenance.validation_outcome == "deterministic"
    assert advice.provenance.provider == "mock"
    assert advice.provenance.input_hash and advice.provenance.input_hash.startswith("sha256:")
    assert not advice.provenance.provider_attempted
    assert not admission.principals


def test_missing_key_falls_back_and_records_selected_provider() -> None:
    admission = RecordingAdmission()
    settings = Settings(environment="test", llm_provider="openai_api")
    advice = _service(settings, admission, lambda _call: pytest.fail("no key")).advise(
        agent=AdvisoryAgentKind.SEARCH_PLANNER,
        requester_id=uuid4(),
        prompt=_prompt(),
        fallback_items=_fallback(),
        parser=_parsed,
    )

    assert advice.items == _fallback()
    assert advice.provenance.provider == "openai_api"
    assert advice.provenance.model == settings.openai_api_model
    assert advice.provenance.error_class == "ProviderNotConfigured"
    assert not admission.principals


def test_success_freezes_selection_before_admission_and_records_safe_provenance() -> None:
    settings = Settings(
        environment="test",
        llm_provider="gemini_api",
        gemini_api_key="secret-before-admission",
    )
    admission = RecordingAdmission(
        on_enter=lambda: setattr(settings, "gemini_api_key", "secret-after-admission")
    )
    captured: list[LlmCall] = []

    def generate(call: LlmCall) -> str:
        captured.append(call)
        return LlmGeneration('{"items":[]}', input_tokens=31, output_tokens=7)

    principal = uuid4()
    advice = _service(settings, admission, generate).advise(
        agent=AdvisoryAgentKind.SEARCH_PLANNER,
        requester_id=principal,
        prompt=_prompt(),
        fallback_items=_fallback(),
        parser=_parsed,
    )

    call = captured[0]
    assert call.api_key == "secret-before-admission"
    assert call.structured_output
    assert call.max_output_tokens == 192
    assert admission.principals == [principal]
    assert admission.reservations[0].committed
    assert advice.items == _parsed("")
    assert advice.provenance.provider_succeeded
    assert advice.provenance.input_token_count == 31
    assert advice.provenance.output_token_count == 7
    assert advice.provenance.validation_outcome == "passed"
    retained = repr(advice)
    assert "secret-before-admission" not in retained
    assert "Synthetic harbour brief" not in retained
    assert '{"items":[]}' not in retained


@pytest.mark.parametrize(
    ("error", "expected_class"),
    [
        (
            AppError(429, "provider_capacity_exhausted", "Synthetic denial."),
            "ProviderAdmissionUnavailable",
        ),
        (RuntimeError("synthetic admission failure"), "ProviderAdmissionUnavailable"),
    ],
)
def test_admission_failures_fall_back_locally(error: Exception, expected_class: str) -> None:
    admission = RecordingAdmission(error=error)
    advice = _service(
        Settings(environment="test", llm_provider="gemini_api", gemini_api_key="secret"),
        admission,
        lambda _call: pytest.fail("admission must precede transport"),
    ).advise(
        agent=AdvisoryAgentKind.SEARCH_PLANNER,
        requester_id=uuid4(),
        prompt=_prompt(),
        fallback_items=_fallback(),
        parser=_parsed,
    )

    assert advice.items == _fallback()
    assert advice.provenance.outcome == "provider_admission_unavailable_fallback"
    assert advice.provenance.error_class == expected_class
    assert not advice.provenance.provider_attempted


def test_transport_and_parser_failures_are_local_and_open_the_circuit() -> None:
    calls = 0

    def fail(_call: LlmCall) -> str:
        nonlocal calls
        calls += 1
        raise RuntimeError("raw transport detail must not be retained")

    settings = Settings(
        environment="test",
        llm_provider="gemini_api",
        gemini_api_key="secret",
        provider_circuit_failure_threshold=1,
    )
    transport_admission = RecordingAdmission()
    service = _service(settings, transport_admission, fail)
    first = service.advise(
        agent=AdvisoryAgentKind.SEARCH_PLANNER,
        requester_id=uuid4(),
        prompt=_prompt(),
        fallback_items=_fallback(),
        parser=_parsed,
    )
    second = service.advise(
        agent=AdvisoryAgentKind.SEARCH_PLANNER,
        requester_id=uuid4(),
        prompt=_prompt(),
        fallback_items=_fallback(),
        parser=_parsed,
    )

    assert first.provenance.error_class == "RuntimeError"
    assert first.provenance.provider_attempted
    assert not transport_admission.reservations[0].committed
    assert "raw transport detail" not in repr(first)
    assert second.provenance.outcome == "circuit_open_fallback"
    assert calls == 1

    parser_admission = RecordingAdmission()
    invalid = _service(
        Settings(environment="test", llm_provider="gemini_api", gemini_api_key="secret"),
        parser_admission,
        lambda _call: "untrusted raw provider output",
    ).advise(
        agent=AdvisoryAgentKind.SEARCH_PLANNER,
        requester_id=uuid4(),
        prompt=_prompt(),
        fallback_items=_fallback(),
        parser=lambda _raw: (_ for _ in ()).throw(ValueError("unsafe parse detail")),
    )
    assert invalid.provenance.outcome == "invalid_output_fallback"
    assert invalid.provenance.validation_outcome == "failed"
    assert invalid.provenance.output_hash
    assert invalid.provenance.error_class == "ProviderOutputValidationError"
    assert parser_admission.reservations[0].committed
    assert "untrusted raw provider output" not in repr(invalid)
    assert "unsafe parse detail" not in repr(invalid)


def test_provider_completed_invalid_response_is_charged() -> None:
    admission = RecordingAdmission()

    def invalid_response(_call: LlmCall) -> str:
        raise AppError(
            502,
            "llm_provider_invalid_response",
            "Synthetic provider response failure.",
        )

    advice = _service(
        Settings(environment="test", llm_provider="gemini_api", gemini_api_key="secret"),
        admission,
        invalid_response,
    ).advise(
        agent=AdvisoryAgentKind.SEARCH_PLANNER,
        requester_id=uuid4(),
        prompt=_prompt(),
        fallback_items=_fallback(),
        parser=_parsed,
    )

    assert admission.reservations[0].committed
    assert advice.provenance.outcome == "invalid_output_fallback"
    assert advice.provenance.validation_outcome == "failed"
    assert advice.provenance.error_class == "AppError:llm_provider_invalid_response"
