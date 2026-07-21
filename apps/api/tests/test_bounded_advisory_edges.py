from uuid import uuid4

import pytest

from coeus.core.config import Settings
from coeus.domain.advisory_agents import (
    MAX_ADVICE_ITEMS,
    AdviceItemKind,
    AdvisoryAgentKind,
    AdvisoryPrompt,
    AgentAdvice,
    AgentAdviceItem,
    AgentAdviceProvenance,
)
from coeus.services.ai_models import AiModelService
from coeus.services.audit import AuditLog
from coeus.services.bounded_advisory import BoundedAdvisoryService


class Reservation:
    def __init__(self) -> None:
        self.committed = False

    def __enter__(self) -> "Reservation":
        return self

    def commit(self) -> None:
        self.committed = True

    def renew(self) -> None:
        return None

    def __exit__(self, *_args: object) -> None:
        return None


class Admission:
    def __init__(self) -> None:
        self.reservation = Reservation()

    def reserve(self, _principal_id: object) -> Reservation:
        return self.reservation


class RaceClosedCircuit:
    def can_attempt(self) -> bool:
        return True

    def try_acquire(self) -> bool:
        return False


def _provenance() -> AgentAdviceProvenance:
    return AgentAdviceProvenance(
        False, False, "local", None, None, None, "not_applicable", "deterministic", "v1", "v1", "v1"
    )


def _item(code: str = "entity") -> AgentAdviceItem:
    return AgentAdviceItem(AdviceItemKind.ENTITY, code, "Synthetic entity", ("title",))


def _prompt() -> AdvisoryPrompt:
    return AdvisoryPrompt("{}", "JSON only.", "v1", "v1", "v1")


def test_domain_contract_enforces_collection_and_reference_bounds() -> None:
    with pytest.raises(ValueError, match="tuple"):
        AgentAdviceItem(AdviceItemKind.ENTITY, "entity", "Detail", ["title"])  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="identifiers"):
        AgentAdviceItem(AdviceItemKind.ENTITY, "entity", "Detail", ("bad ref",))
    with pytest.raises(ValueError, match="unique"):
        AgentAdviceItem(AdviceItemKind.ENTITY, "entity", "Detail", ("title", "title"))
    with pytest.raises(ValueError, match="bounded tuple"):
        AgentAdvice(AdvisoryAgentKind.SEARCH_PLANNER, [_item()], _provenance())  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="invalid item"):
        AgentAdvice(AdvisoryAgentKind.SEARCH_PLANNER, ("bad",), _provenance())  # type: ignore[arg-type]
    duplicate = (_item(), AgentAdviceItem(AdviceItemKind.ENTITY, "entity", "Other"))
    with pytest.raises(ValueError, match="duplicate"):
        AgentAdvice(AdvisoryAgentKind.SEARCH_PLANNER, duplicate, _provenance())
    maximum = tuple(_item(f"entity_{index}") for index in range(MAX_ADVICE_ITEMS))
    assert len(AgentAdvice(AdvisoryAgentKind.SEARCH_PLANNER, maximum, _provenance()).items) == 32
    with pytest.raises(ValueError, match="bounded tuple"):
        AgentAdvice(AdvisoryAgentKind.SEARCH_PLANNER, (*maximum, _item("extra")), _provenance())
    with pytest.raises(ValueError, match="always be shadow-only"):
        AgentAdvice(AdvisoryAgentKind.ROUTING_CRITIC, (), _provenance())
    with pytest.raises(ValueError, match="Only the routing critic"):
        AgentAdvice(
            AdvisoryAgentKind.SEARCH_PLANNER,
            (),
            _provenance(),
            shadow_only=True,
        )


@pytest.mark.parametrize(
    "prompt",
    [
        lambda: AdvisoryPrompt("", "JSON", "v1", "v1", "v1"),
        lambda: AdvisoryPrompt("{}", "", "v1", "v1", "v1"),
        lambda: AdvisoryPrompt("{}", "JSON", "invalid version", "v1", "v1"),
    ],
)
def test_prompt_contract_rejects_invalid_bounds(prompt: object) -> None:
    with pytest.raises(ValueError):
        prompt()  # type: ignore[operator]


def test_runtime_model_selection_and_circuit_race_are_bounded() -> None:
    settings = Settings(environment="test")
    models = AiModelService(settings, AuditLog())
    models.configure_api_key("admin", "admin@example.test", "secret")
    models.select_provider("admin", "admin@example.test", "gemini_api")
    admission = Admission()
    captured: list[str] = []
    service = BoundedAdvisoryService(
        settings,
        models,
        admission,
        text_generator=lambda call: captured.append(call.provider) or "{}",
    )
    advice = service.advise(
        agent=AdvisoryAgentKind.SEARCH_PLANNER,
        requester_id=uuid4(),
        prompt=_prompt(),
        fallback_items=(_item(),),
        parser=lambda _raw: (_item("planned"),),
    )
    assert captured == ["gemini_api"]
    assert advice.provenance.provider_succeeded

    raced = BoundedAdvisoryService(settings, models, admission)
    raced._circuit = RaceClosedCircuit()  # type: ignore[assignment]
    fallback = raced.advise(
        agent=AdvisoryAgentKind.SEARCH_PLANNER,
        requester_id=uuid4(),
        prompt=_prompt(),
        fallback_items=(_item(),),
        parser=lambda _raw: (),
    )
    assert fallback.provenance.outcome == "circuit_open_fallback"
