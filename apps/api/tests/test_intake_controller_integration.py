import json

import pytest
from httpx import ASGITransport, AsyncClient

from coeus.core.config import Settings
from coeus.domain.tickets import IntakeDetails
from coeus.main import create_app
from coeus.services.configurable_intake_provider import ConfigurableIntakeProvider
from ticket_api_helpers import login


def _complete_intake(**updates: str) -> IntakeDetails:
    values = {
        "title": "Synthetic regional activity",
        "description": "Assess synthetic activity and likely disruption.",
        "operational_question": "What activity needs command attention?",
        "area_or_region": "Baltic ports",
        "time_period_start": "2026-08-02",
        "time_period_end": "2026-07-01",
        "priority": "routine",
        "requesting_unit": "Synthetic Unit Atlas",
        "intelligence_disciplines": "OSINT",
        "required_output_format": "Briefing note",
        "customer_success_criteria": "Identify actions for watch teams.",
    }
    values.update(updates)
    return IntakeDetails(**values, missing_information=())


def test_controller_keeps_proven_contradiction_open_and_allows_human_ambiguity_override() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    actor = app.state.access_services.repository.get_user_by_username("user@example.test")
    assert actor is not None
    service = app.state.ticket_services.conversations

    contradiction, contradiction_status = service._reply_and_status(
        actor, "open", "Those are the details.", _complete_intake()
    )
    refused_close, refused_close_status = service._reply_and_status(
        actor, "open", "Please finish here.", _complete_intake()
    )
    ambiguity, ambiguity_status = service._reply_and_status(
        actor,
        "open",
        "Those are the details.",
        _complete_intake(
            area_or_region="global",
            time_period_start="2026-07-01",
            time_period_end="2026-08-02",
        ),
    )
    closed, closed_status = service._reply_and_status(
        actor,
        "open",
        "Please finish here.",
        _complete_intake(
            area_or_region="global",
            time_period_start="2026-07-01",
            time_period_end="2026-08-02",
        ),
    )

    assert contradiction_status == "open"
    assert contradiction.text == (
        "The start date is after the end date. What date range should be used?"
    )
    assert refused_close_status == "open"
    assert refused_close.outcome == "close_refused_intake_contradiction"
    assert "What date range should be used?" in refused_close.text
    assert ambiguity_status == "open"
    assert "within that region" in ambiguity.text
    assert closed_status == "closed"
    assert "completes the intake" in closed.text.casefold()


def test_provider_cannot_suppress_a_deterministic_contradiction() -> None:
    settings = Settings(
        environment="test",
        llm_provider="gemini_api",
        gemini_api_key="synthetic-key",
    )
    proposed_completion = json.dumps(
        {
            "action": "confirm_complete",
            "strategy": "review_complete",
            "reason_codes": ["intake_complete"],
            "suggested_field": None,
            "abstain": False,
        }
    )
    provider = ConfigurableIntakeProvider(
        settings,
        None,
        text_generator=lambda _call: proposed_completion,
    )

    reply = provider.build_admitted_assistant_message(_complete_intake(), ())

    assert reply.outcome == "controller_override_fallback"
    assert reply.validation_outcome == "passed"
    assert reply.fallback_outcome == "deterministic"
    assert reply.error_class == "ControllerOverride"
    assert reply.plan is not None and reply.plan.contradictions
    assert reply.text.startswith("The start date is after the end date.")


def test_unexpected_provider_failure_uses_the_deterministic_fallback() -> None:
    settings = Settings(
        environment="test",
        llm_provider="gemini_api",
        gemini_api_key="synthetic-key",
    )

    def fail(_call: object) -> str:
        raise RuntimeError("synthetic provider failure")

    reply = ConfigurableIntakeProvider(
        settings,
        None,
        text_generator=fail,
    ).build_admitted_assistant_message(_complete_intake(), ())

    assert not reply.provider_succeeded
    assert reply.outcome == "provider_error_fallback"
    assert reply.error_class == "RuntimeError"
    assert reply.plan is not None and reply.plan.contradictions


@pytest.mark.asyncio
async def test_reversed_dates_are_not_ready_and_cannot_be_submitted() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        session = await login(client)
        created = await client.post(
            "/api/v1/chat/messages",
            headers={"X-CSRF-Token": str(session["csrfToken"])},
            json={"message": "Need a synthetic regional activity briefing."},
        )
        ticket_id = created.json()["id"]
        intake = _complete_intake()
        edited = await client.patch(
            f"/api/v1/tickets/{ticket_id}/intake",
            headers={"X-CSRF-Token": str(session["csrfToken"])},
            json={
                "title": intake.title,
                "description": intake.description,
                "operationalQuestion": intake.operational_question,
                "areaOrRegion": intake.area_or_region,
                "timePeriodStart": intake.time_period_start,
                "timePeriodEnd": intake.time_period_end,
                "priority": intake.priority,
                "requestingUnit": intake.requesting_unit,
                "intelligenceDisciplines": intake.intelligence_disciplines,
                "requiredOutputFormat": intake.required_output_format,
                "customerSuccessCriteria": intake.customer_success_criteria,
            },
        )
        submitted = await client.post(
            f"/api/v1/tickets/{ticket_id}/submit",
            headers={"X-CSRF-Token": str(session["csrfToken"])},
        )

    assert edited.status_code == 200
    assert edited.json()["isReadyForSubmission"] is False
    assert submitted.status_code == 409
    assert submitted.json()["error"]["code"] == "intake_contradiction"
