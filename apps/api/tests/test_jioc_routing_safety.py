from dataclasses import replace
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from coeus.core.config import Settings
from coeus.domain.enums import TicketState
from coeus.domain.jioc_routing import (
    ROUTING_RELEASE,
    JiocRoutingMode,
    RoutingOperationalSnapshot,
)
from coeus.domain.search_metrics import RfiSearchMetrics
from coeus.domain.tickets import AgentExecutionKind, IntakeDetails, TicketRecord
from coeus.services.jioc_routing_agent import JiocRoutingAgentService
from coeus.services.tasking_consent import TaskingConsentService
from coeus.services.ticket_records import timeline


def test_routing_defaults_active_with_the_evaluated_release() -> None:
    settings = Settings(environment="test")

    assert settings.jioc_agent_routing_enabled is JiocRoutingMode.ACTIVE
    assert settings.jioc_routing_approved_releases == [ROUTING_RELEASE]
    settings.require_runtime_security()


def test_active_routing_rejects_an_unapproved_release() -> None:
    with pytest.raises(ValueError, match="JIOC_ROUTING_APPROVED_RELEASES"):
        Settings(
            environment="test",
            jioc_agent_routing_enabled=JiocRoutingMode.ACTIVE,
            jioc_routing_approved_releases=[],
        ).require_runtime_security()


def test_legacy_true_environment_value_requires_explicit_release_approval(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("COEUS_ENVIRONMENT", "test")
    monkeypatch.setenv("COEUS_JIOC_AGENT_ROUTING_ENABLED", "true")
    monkeypatch.delenv("COEUS_JIOC_ROUTING_APPROVED_RELEASES", raising=False)
    settings = Settings(_env_file=None)

    assert settings.jioc_agent_routing_enabled is True
    assert settings.jioc_routing_approved_releases == [ROUTING_RELEASE]
    with pytest.raises(ValueError, match="JIOC_ROUTING_APPROVED_RELEASES must be explicit"):
        settings.require_runtime_security()


@pytest.mark.parametrize(
    ("mode", "expected_action"),
    (
        (JiocRoutingMode.DISABLED, "defer"),
        (JiocRoutingMode.SHADOW, False),
        (JiocRoutingMode.ACTIVE, True),
        (False, "defer"),
        (True, True),
    ),
)
def test_tasking_consent_enforces_rollout_authority(
    mode: JiocRoutingMode | bool, expected_action: bool | str
) -> None:
    pending = _ticket("Assess the reports.", "assessment report")
    lifecycle = MagicMock()
    lifecycle.no_match_consent.return_value = pending
    routing = MagicMock()
    routing.route.return_value = pending
    routing.defer_to_manager.return_value = pending
    service = TaskingConsentService(lifecycle, routing, mode)

    result = service.decide(SimpleNamespace(), pending.ticket_id, True)

    assert result is pending
    if expected_action == "defer":
        routing.route.assert_not_called()
        routing.defer_to_manager.assert_called_once_with(pending.ticket_id)
    else:
        routing.defer_to_manager.assert_not_called()
        routing.route.assert_called_once_with(pending.ticket_id, apply=expected_action)


def test_tasking_consent_agent_failure_refers_to_human_review() -> None:
    pending = _ticket("Assess reports.", "assessment report")
    referred = replace(pending, state=TicketState.JIOC_REVIEW)
    lifecycle = MagicMock()
    lifecycle.no_match_consent.return_value = pending
    routing = MagicMock()
    routing.route.side_effect = RuntimeError("synthetic agent failure")
    routing.defer_to_manager.return_value = referred
    service = TaskingConsentService(lifecycle, routing, JiocRoutingMode.ACTIVE)

    result = service.decide(SimpleNamespace(), pending.ticket_id, True)

    assert result is referred
    routing.defer_to_manager.assert_called_once_with(
        pending.ticket_id,
        reason="routing_agent_failed",
    )


def test_tasking_consent_returns_pending_only_when_agent_and_referral_fail() -> None:
    pending = _ticket("Assess reports.", "assessment report")
    lifecycle = MagicMock()
    lifecycle.no_match_consent.return_value = pending
    routing = MagicMock()
    routing.route.side_effect = RuntimeError("synthetic agent failure")
    routing.defer_to_manager.side_effect = RuntimeError("synthetic referral failure")

    result = TaskingConsentService(
        lifecycle,
        routing,
        JiocRoutingMode.ACTIVE,
    ).decide(SimpleNamespace(), pending.ticket_id, True)

    assert result is pending


def test_missing_operational_evidence_fails_closed_to_manager_review() -> None:
    ticket = _ticket("Assess the available reporting.", "assessment report")
    service, mutations = _service(ticket)

    result = service.route(ticket.ticket_id)

    assert result.state == TicketState.JIOC_REVIEW
    assert "availability_snapshot_missing" in result.jioc_routing_decisions[-1].rationale_codes
    mutations.save_audited_with_outbox_if_current.assert_called_once()
    intent = mutations.save_audited_with_outbox_if_current.call_args.args[-1][0]
    assert intent.event_type == "jioc_routing_critique_requested"
    assert intent.payload["decision_id"] == str(result.jioc_routing_decisions[-1].decision_id)


def test_disabled_referral_invokes_no_agent_and_records_no_agent_decision() -> None:
    ticket = _ticket("Assess the available reporting.", "assessment report")
    rfa = MagicMock()
    cm = MagicMock()
    service, mutations = _service(ticket, rfa_agent=rfa, cm_agent=cm)

    result = service.defer_to_manager(ticket.ticket_id)

    assert result.state == TicketState.JIOC_REVIEW
    assert result.jioc_routing_decisions == ()
    assert result.agent_runs == ()
    rfa.review.assert_not_called()
    cm.review.assert_not_called()
    mutations.save_audited_if_current.assert_called_once()

    service._tickets.tickets.assignment_snapshot.return_value = (result,)
    unchanged = service.defer_to_manager(result.ticket_id)
    assert unchanged is result


def test_shadow_mode_records_once_and_refers_to_human_review() -> None:
    ticket = _ticket("Assess the available reporting.", "assessment report")
    service, mutations = _service(ticket, _AvailableContext())

    first = service.route(ticket.ticket_id, apply=False)
    service._tickets.tickets.assignment_snapshot.return_value = (first,)
    second = service.route(ticket.ticket_id, apply=False)

    assert first.state == TicketState.JIOC_REVIEW
    assert first.jioc_routing_decisions[-1].disposition == "shadow_recommendation"
    assert first.rfa_reviews[-1].manager_review_required is True
    assert first.messages == ticket.messages
    assert first.clarification_requests == ticket.clarification_requests
    assert first.timeline == ticket.timeline
    assert {run.agent_name for run in first.agent_runs} == {
        "rfa-capability-agent",
        "cm-capability-agent",
        "orchestrator-agent",
        "jioc-routing-agent",
    }
    assert all(run.execution_kind is AgentExecutionKind.DETERMINISTIC for run in first.agent_runs)
    assert all(run.input_hash and run.output_hash for run in first.agent_runs)
    assert second is first
    mutations.save_audited_with_outbox_if_current.assert_called_once()


def test_shadow_clarification_records_evidence_without_customer_handoff() -> None:
    ticket = _ticket("Assess activity on Mars.", "assessment report")
    service, _mutations = _service(ticket, _AvailableContext())

    result = service.route(ticket.ticket_id, apply=False)

    assert result.state == TicketState.JIOC_REVIEW
    assert result.jioc_routing_decisions[-1].required_clarifications
    assert result.messages == ticket.messages
    assert result.clarification_requests == ticket.clarification_requests
    assert result.timeline == ticket.timeline
    assert "customer-chatbot-agent" not in {run.agent_name for run in result.agent_runs}


def test_unsupported_scope_requests_clarification_instead_of_routing() -> None:
    ticket = _ticket("Assess activity on Mars.", "assessment report")
    service, _mutations = _service(ticket, _AvailableContext())

    result = service.route(ticket.ticket_id)

    assert result.state == TicketState.INFO_REQUIRED
    assert result.jioc_routing_decisions[-1].evidence_outcome == "clarification_required"


def _ticket(
    description: str,
    output_format: str,
    now: datetime | None = None,
    *,
    priority: str = "routine",
    deadline: str | None = "2026-07-21",
    restrictions: str | None = None,
    product_offer_unresolved: bool = False,
    active_work_completed: bool = True,
    active_work_offer_unresolved: bool = False,
) -> TicketRecord:
    created = now or datetime.now(UTC)
    ticket_id = uuid4()
    metric = RfiSearchMetrics(
        uuid4(),
        "synthetic query",
        0,
        0,
        0,
        None,
        created,
        outcome="no_match",
        assurance="definitive",
        coverage_status="complete",
        corpus_version="routing-eval-corpus-v1",
    )
    product_offers = (
        (
            SimpleNamespace(
                product_id=uuid4(),
                status=SimpleNamespace(value="offered"),
            ),
        )
        if product_offer_unresolved
        else ()
    )
    active_work_offers = (
        (SimpleNamespace(ticket_id=uuid4(), status="offered"),)
        if active_work_offer_unresolved
        else ()
    )
    active_timeline = (
        (
            timeline(
                ticket_id,
                uuid4(),
                "active_work_search_completed",
                "No matching active work found.",
            ),
        )
        if active_work_completed
        else ()
    )
    return TicketRecord(
        ticket_id,
        "RFI-ROUTING-EVAL",
        uuid4(),
        TicketState.JIOC_ROUTING_PENDING,
        IntakeDetails(
            title="Synthetic routing evaluation",
            description=description,
            operational_question="What action is required?",
            area_or_region="Mock Region",
            priority=priority,
            deadline=deadline,
            required_output_format=output_format,
            restrictions_or_caveats=restrictions,
            customer_success_criteria="Support a synthetic decision.",
        ),
        product_offers=product_offers,
        active_work_offers=active_work_offers,
        search_metrics=(metric,),
        timeline=active_timeline,
    )


def _service(
    ticket: TicketRecord,
    operational_context=None,
    rfa_agent=None,
    cm_agent=None,
) -> tuple[JiocRoutingAgentService, MagicMock]:
    mutations = MagicMock()
    mutations.save_audited_if_current.side_effect = lambda _current, proposed, *_args: proposed
    mutations.save_audited_with_outbox_if_current.side_effect = lambda _current, proposed, *_args: (
        proposed
    )
    tickets = SimpleNamespace(tickets=MagicMock(), mutations=mutations)
    tickets.tickets.assignment_snapshot.return_value = (ticket,)
    return (
        JiocRoutingAgentService(
            tickets,
            operational_context=operational_context,
            rfa_agent=rfa_agent,
            cm_agent=cm_agent,
        ),
        mutations,
    )


class _AvailableContext:
    def snapshot(
        self, _ticket: TicketRecord, candidate_team_ids: tuple[str, ...]
    ) -> RoutingOperationalSnapshot:
        return RoutingOperationalSnapshot(
            "capability-catalogue-v1",
            datetime.now(UTC),
            tuple(f"{team_id}:available:1" for team_id in candidate_team_ids),
        )
