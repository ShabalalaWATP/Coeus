from uuid import uuid4

from coeus.core.config import Settings
from coeus.domain.advisory_agents import (
    AdviceItemKind,
    AdvisoryAgentKind,
    AdvisoryPrompt,
    AgentAdviceItem,
)
from coeus.services.bounded_advisory import BoundedAdvisoryService


class _Reservation:
    def __enter__(self) -> "_Reservation":
        return self

    def commit(self) -> None:
        return None

    def renew(self) -> None:
        return None

    def __exit__(self, *_args: object) -> None:
        return None


class _Admission:
    def __init__(self) -> None:
        self.principals: list[object] = []

    def reserve(self, principal_id: object) -> _Reservation:
        self.principals.append(principal_id)
        return _Reservation()


def test_hosted_remote_egress_requires_per_agent_release_approval() -> None:
    admission = _Admission()
    calls = 0

    def generate(_call: object) -> str:
        nonlocal calls
        calls += 1
        return "{}"

    prompt = AdvisoryPrompt("{}", "JSON only.", "v1", "v1", "v1")
    fallback = (AgentAdviceItem(AdviceItemKind.ENTITY, "entity", "Synthetic entity"),)
    parser = lambda _raw: fallback  # noqa: E731
    blocked = BoundedAdvisoryService(
        Settings(
            environment="dev",
            llm_provider="gemini_api",
            gemini_api_key="synthetic-key",
        ),
        None,
        admission,  # type: ignore[arg-type]
        text_generator=generate,  # type: ignore[arg-type]
    ).advise(
        agent=AdvisoryAgentKind.SEARCH_PLANNER,
        requester_id=uuid4(),
        prompt=prompt,
        fallback_items=fallback,
        parser=parser,
    )
    approved = BoundedAdvisoryService(
        Settings(
            environment="dev",
            llm_provider="gemini_api",
            gemini_api_key="synthetic-key",
            search_planner_remote_enabled=True,
            advisory_approved_providers=["gemini_api"],
            advisory_approved_data_classifications=["synthetic"],
        ),
        None,
        admission,  # type: ignore[arg-type]
        text_generator=lambda _call: "{}",
    ).advise(
        agent=AdvisoryAgentKind.SEARCH_PLANNER,
        requester_id=uuid4(),
        prompt=prompt,
        fallback_items=fallback,
        parser=parser,
    )

    assert blocked.provenance.outcome == "remote_egress_not_approved_fallback"
    assert blocked.provenance.error_class == "AgentRemoteEgressNotApproved"
    assert len(admission.principals) == 1
    assert calls == 0
    assert approved.provenance.outcome == "provider_success"
