import json
from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from coeus.core.config import Settings
from coeus.domain.access import ProductStatus
from coeus.domain.advisory_agents import (
    AdviceItemKind,
    AdvisoryAgentKind,
    AgentAdvice,
    AgentAdviceItem,
    AgentAdviceProvenance,
)
from coeus.domain.enums import TicketState
from coeus.domain.jioc_routing import ROUTING_RELEASE, RoutingOperationalSnapshot
from coeus.domain.search_index import GroundedSearchResult
from coeus.domain.search_metrics import RfiSearchMetrics
from coeus.domain.tickets import TicketRecord
from coeus.main import create_app
from coeus.repositories.auth import SeedUserRepository
from coeus.repositories.tickets import InMemoryTicketRepository
from coeus.services.audit import AuditLog
from coeus.services.configurable_intake_provider import ConfigurableIntakeProvider
from coeus.services.intake import IntakeExtractionService, RequirementCompletenessService
from coeus.services.passwords import PasswordHasher
from coeus.services.provider_admission import ProviderAdmissionController
from coeus.services.routing_oversight import RoutingOversightService
from coeus.services.search_planner import SearchPlannerAdvice
from coeus.services.search_planner_agent import SearchPlan
from coeus.services.ticket_conversations import ConversationService
from coeus.services.ticket_records import timeline
from coeus.services.tickets import TicketService
from rfi_search_helpers import login, submitted_ticket


def _provenance(**updates: object) -> AgentAdviceProvenance:
    value = AgentAdviceProvenance(
        provider_attempted=True,
        provider_succeeded=True,
        outcome="provider_success",
        provider="synthetic",
        model="bounded-test-model",
        duration_ms=1,
        fallback_outcome="not_used",
        validation_outcome="passed",
        prompt_version="planner-v1",
        policy_version="controller-v1",
        context_schema_version="context-v1",
        input_hash="sha256:" + "a" * 64,
        output_hash="sha256:" + "b" * 64,
        input_token_count=10,
        output_token_count=5,
    )
    return replace(value, **updates)


def test_intake_provider_cannot_change_controller_lifecycle() -> None:
    settings = Settings(
        environment="test",
        argon2_memory_cost=8_192,
        llm_provider="gemini_api",
        gemini_api_key="synthetic-key",
    )
    users = SeedUserRepository(settings, PasswordHasher(settings))
    actor = users.get_by_username("user@example.test")
    assert actor is not None
    repository = InMemoryTicketRepository()
    audit = AuditLog()
    tickets = TicketService(repository, RequirementCompletenessService(), audit)

    def malicious_reply(_call: object) -> str:
        return json.dumps(
            {
                "action": "confirm_complete",
                "strategy": "review_complete",
                "reason_codes": ["intake_complete"],
                "suggested_field": None,
                "abstain": False,
                "target_state": "CLOSED_EXISTING_PRODUCT_ACCEPTED",
            }
        )

    service = ConversationService(
        repository,
        tickets,
        tickets.mutations,
        IntakeExtractionService(),
        ConfigurableIntakeProvider(settings, None, text_generator=malicious_reply),
        audit,
        ProviderAdmissionController(
            max_concurrent=1,
            max_calls_per_window=5,
            max_calls_per_principal=5,
            window_seconds=60,
        ),
    )

    result = service.send_message(actor, "Need a synthetic briefing.")

    assert result.state is TicketState.INFO_REQUIRED
    assert result.intake.missing_information
    assert result.agent_runs[-1].validation_outcome == "failed"
    assert result.agent_runs[-1].fallback_outcome == "deterministic"
    assert result.agent_runs[-1].advice is not None
    assert "target_state" not in repr(result.agent_runs[-1].advice)


@pytest.mark.asyncio
async def test_search_advice_reaches_both_retrievers_without_access_or_assurance_authority(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        session = await login(client, "user@example.test")
        ticket_id = await submitted_ticket(client, str(session["csrfToken"]))
        actor = app.state.access_services.repository.get_user_by_username("user@example.test")
        assert actor is not None
        ticket = app.state.ticket_services.tickets.get_visible_ticket(actor, UUID(ticket_id))
        app.state.ticket_services.tickets.save_system_update(
            replace(ticket, state=TicketState.RFI_SEARCHING, product_offers=(), search_metrics=())
        )

        advice = SearchPlannerAdvice(
            query_expansions=("status:draft",),
            alternative_terminology=("classification:any",),
        )
        record = AgentAdvice(
            AdvisoryAgentKind.SEARCH_PLANNER,
            (
                AgentAdviceItem(
                    AdviceItemKind.QUERY_EXPANSION, "query_expansion_1", "status:draft"
                ),
                AgentAdviceItem(
                    AdviceItemKind.ALTERNATIVE_TERMINOLOGY,
                    "alternative_terminology_1",
                    "classification:any",
                ),
            ),
            _provenance(),
        )
        monkeypatch.setattr(
            app.state.rfi_search_service._planner,
            "plan",
            lambda _requester_id, _intake: SearchPlan(advice, record),
        )
        observed: dict[str, object] = {}

        def hybrid(requester, filters, query, _embedding):  # type: ignore[no-untyped-def]
            observed["legacy_actor"] = requester
            observed["legacy_filters"] = filters
            observed.setdefault("legacy_queries", []).append(query)  # type: ignore[union-attr]
            return ()

        def grounded(requester, _intake, _principal_id, *, planned_query=None):  # type: ignore[no-untyped-def]
            observed["grounded_actor"] = requester
            observed.setdefault("grounded_queries", []).append(planned_query)  # type: ignore[union-attr]
            return GroundedSearchResult((), "hybrid", None, "space-v1", "complete", "corpus-v1")

        monkeypatch.setattr(app.state.rfi_search_service._store_search, "hybrid_candidates", hybrid)
        monkeypatch.setattr(app.state.rfi_search_service._grounded, "search", grounded)
        response = await client.post(
            f"/api/v1/rfi-search/{ticket_id}/run",
            headers={"X-CSRF-Token": str(session["csrfToken"])},
        )

    assert response.status_code == 200
    assert observed["legacy_queries"] == observed["grounded_queries"]
    queries = observed["legacy_queries"]
    assert isinstance(queries, list) and len(queries) == 2
    assert "status:draft" not in queries[0]
    assert "status:draft" in queries[1]
    assert observed["legacy_actor"] == observed["grounded_actor"] == actor
    assert observed["legacy_filters"].status is ProductStatus.PUBLISHED
    assert response.json()["assurance"] == "definitive"
    assert response.json()["outcome"] == "no_match"
    assert "status:draft" not in response.json()["metrics"]["query"]


@pytest.mark.asyncio
async def test_routing_critic_is_post_commit_idempotent_and_failure_safe() -> None:
    app = create_app(_routing_settings())
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        session = await login(client, "user@example.test")
        first_id = await submitted_ticket(client, str(session["csrfToken"]))
        second_id = await submitted_ticket(client, str(session["csrfToken"]))

    first = _prepare_route(app, first_id)
    critic = _RecordingCritic()
    app.state.jioc_routing_agent_service._critic = critic
    routed = app.state.jioc_routing_agent_service.route(first.ticket_id)
    repeated = app.state.jioc_routing_agent_service.route(first.ticket_id)

    assert critic.observed == [(TicketState.ANALYST_ASSIGNMENT, 1)]
    assert routed.state is repeated.state is TicketState.ANALYST_ASSIGNMENT
    assert routed.jioc_routing_decisions == repeated.jioc_routing_decisions
    routing_advice = [
        run
        for run in repeated.agent_runs
        if run.advice is not None and run.advice.agent is AdvisoryAgentKind.ROUTING_CRITIC
    ]
    assert len(routing_advice) == 1
    stale = replace(
        repeated,
        jioc_routing_decisions=(
            *repeated.jioc_routing_decisions,
            replace(repeated.jioc_routing_decisions[-1], decision_id=uuid4()),
        ),
    )
    assert RoutingOversightService._task(stale).critic_verdict is None

    second = _prepare_route(app, second_id)
    app.state.jioc_routing_agent_service._critic = _FailingCritic()
    failed_critique = app.state.jioc_routing_agent_service.route(second.ticket_id)
    persisted = app.state.ticket_services.tickets._repository.get(second.ticket_id)

    assert failed_critique.state is TicketState.ANALYST_ASSIGNMENT
    assert len(failed_critique.jioc_routing_decisions) == 1
    assert persisted is not None
    assert persisted.state is TicketState.ANALYST_ASSIGNMENT
    assert persisted.jioc_routing_decisions == failed_critique.jioc_routing_decisions


@pytest.mark.parametrize(
    "updates",
    [
        {"outcome": "x" * 65},
        {"provider": "x" * 129},
        {"duration_ms": -1},
        {"input_hash": "sha256:not-a-hash"},
        {"output_token_count": 2_147_483_648},
    ],
)
def test_advice_provenance_rejects_unbounded_values(updates: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        _provenance(**updates)


@pytest.mark.parametrize(
    "references",
    [("decision:one", "decision:one"), tuple(f"decision:{index}" for index in range(9))],
)
def test_agent_advice_rejects_invalid_context_reference_sets(
    references: tuple[str, ...],
) -> None:
    with pytest.raises(ValueError):
        AgentAdvice(
            AdvisoryAgentKind.ROUTING_CRITIC,
            (),
            _provenance(),
            shadow_only=True,
            context_references=references,
        )


class _RecordingCritic:
    def __init__(self) -> None:
        self.observed: list[tuple[TicketState, int]] = []

    def critique(self, _requester_id: UUID, ticket: TicketRecord) -> AgentAdvice:
        self.observed.append((ticket.state, len(ticket.jioc_routing_decisions)))
        decision = ticket.jioc_routing_decisions[-1]
        return AgentAdvice(
            AdvisoryAgentKind.ROUTING_CRITIC,
            (),
            _provenance(),
            verdict="supports",
            shadow_only=True,
            context_references=(f"decision:{decision.decision_id}",),
        )


class _FailingCritic:
    def critique(self, _requester_id: UUID, _ticket: TicketRecord) -> AgentAdvice:
        raise RuntimeError("synthetic critic failure")


def _prepare_route(app: FastAPI, ticket_id: str) -> TicketRecord:
    app.state.jioc_deterministic_routing_service._operational_context = _OperationalContext()
    ticket = app.state.ticket_services.tickets._repository.get(UUID(ticket_id))
    assert ticket is not None
    now = datetime.now(UTC)
    metric = RfiSearchMetrics(
        uuid4(),
        "synthetic route",
        0,
        0,
        0,
        None,
        now,
        outcome="no_match",
        assurance="definitive",
        coverage_status="complete",
        corpus_version="corpus-v1",
    )
    prepared = replace(
        ticket,
        state=TicketState.JIOC_ROUTING_PENDING,
        intake=replace(ticket.intake, description="Assess the available reporting."),
        product_offers=(),
        active_work_offers=(),
        search_metrics=(metric,),
        timeline=(
            *ticket.timeline,
            timeline(
                ticket.ticket_id,
                ticket.requester_user_id,
                "active_work_search_completed",
                "No matching active work found.",
            ),
        ),
    )
    app.state.ticket_services.tickets.save_system_update(prepared)
    return prepared


class _OperationalContext:
    def snapshot(
        self, _ticket: TicketRecord, candidate_team_ids: tuple[str, ...]
    ) -> RoutingOperationalSnapshot:
        return RoutingOperationalSnapshot(
            "capability-catalogue-v1",
            datetime.now(UTC),
            tuple(f"{team_id}:available:1" for team_id in candidate_team_ids),
        )


def _routing_settings() -> Settings:
    return Settings(
        environment="test",
        argon2_memory_cost=8_192,
        persistence_provider="memory",
        jioc_agent_routing_enabled="active",
        jioc_routing_approved_releases=[ROUTING_RELEASE],
    )
