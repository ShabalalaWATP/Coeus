from typing import cast
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient

from coeus.core.config import Settings
from coeus.domain.tickets import TicketRecord
from coeus.main import create_app

SEED_CREDENTIAL = "CoeusLocal1!"


async def login(client: AsyncClient, username: str) -> dict[str, object]:
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": SEED_CREDENTIAL},
    )
    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, dict)
    return cast(dict[str, object], payload)


async def submitted_ticket(
    client: AsyncClient,
    csrf_token: str,
    *,
    title: str,
    question: str,
    region: str,
    description: str,
    output_format: str,
) -> str:
    created = await client.post(
        "/api/v1/chat/messages",
        headers={"X-CSRF-Token": csrf_token},
        json={"message": f"{title}. {question}"},
    )
    assert created.status_code == 201
    ticket_id = created.json()["id"]
    edited = await client.patch(
        f"/api/v1/tickets/{ticket_id}/intake",
        headers={"X-CSRF-Token": csrf_token},
        json={
            "title": title,
            "description": description,
            "operationalQuestion": question,
            "areaOrRegion": region,
            "timePeriodStart": "2026-06-01",
            "priority": "routine",
            "requestingUnit": "Carrier Strike Group Atlas",
            "intelligenceDisciplines": "IMINT",
            "requiredOutputFormat": output_format,
            "customerSuccessCriteria": "Identify activity requiring attention.",
        },
    )
    submitted = await client.post(
        f"/api/v1/tickets/{ticket_id}/submit",
        headers={"X-CSRF-Token": csrf_token},
    )
    assert edited.status_code == 200
    assert submitted.status_code == 200
    return str(ticket_id)


async def similar_ticket_pair(client: AsyncClient, csrf_token: str) -> tuple[str, str]:
    target_id = await submitted_ticket(
        client,
        csrf_token,
        title="Vessel movements Gulf of Finland",
        question="What vessel movements are occurring around the Gulf of Finland?",
        region="Gulf of Finland",
        description="Track vessel movements near the Gulf of Finland.",
        output_format="movement report",
    )
    source_id = await submitted_ticket(
        client,
        csrf_token,
        title="Boat traffic near St Petersburg",
        question="What boat traffic is near St Petersburg?",
        region="St Petersburg",
        description="Assess boat traffic near St Petersburg.",
        output_format="traffic picture",
    )
    return source_id, target_id


async def test_customer_sees_visible_similar_ticket_and_can_join_owned_match() -> None:
    app = create_app(
        Settings(environment="test", argon2_memory_cost=8_192, persistence_provider="memory")
    )
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        user = await login(client, "user@example.test")
        source_id, target_id = await similar_ticket_pair(client, str(user["csrfToken"]))
        notice = await client.get(f"/api/v1/similar-requests/tickets/{source_id}")
        joined = await client.post(
            f"/api/v1/similar-requests/tickets/{source_id}/join/{target_id}",
            headers={"X-CSRF-Token": str(user["csrfToken"])},
        )

    assert notice.status_code == 200
    payload = notice.json()
    assert set(payload) == {"matches"}
    assert payload["matches"][0]["ticketId"] == target_id
    assert payload["matches"][0]["score"] >= 0.58
    assert any(
        reason.startswith("similarity:vector:") for reason in payload["matches"][0]["reasons"]
    )
    assert joined.status_code == 200
    assert joined.json()["joinedTicketId"] == target_id
    audit_types = [event.event_type for event in app.state.auth_service.audit_log.list_events()]
    assert "similar_request_notified" in audit_types


async def test_customer_cannot_see_hidden_similar_ticket_detail() -> None:
    app = create_app(
        Settings(environment="test", argon2_memory_cost=8_192, persistence_provider="memory")
    )
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        colleague = await login(client, "colleague@example.test")
        await submitted_ticket(
            client,
            str(colleague["csrfToken"]),
            title="Vessel movements Gulf of Finland",
            question="What vessel movements are occurring around the Gulf of Finland?",
            region="Gulf of Finland",
            description="Track vessel movements near the Gulf of Finland.",
            output_format="movement report",
        )
        user = await login(client, "user@example.test")
        source_id = await submitted_ticket(
            client,
            str(user["csrfToken"]),
            title="Boat traffic near St Petersburg",
            question="What boat traffic is near St Petersburg?",
            region="St Petersburg",
            description="Assess boat traffic near St Petersburg.",
            output_format="traffic picture",
        )
        notice = await client.get(f"/api/v1/similar-requests/tickets/{source_id}")

    # The customer path carries zero hidden-ticket signal: no matches, no boolean, no count,
    # and no audit event that would confirm the invisible ticket exists.
    assert notice.status_code == 200
    assert notice.json() == {"matches": []}
    audit_types = [event.event_type for event in app.state.auth_service.audit_log.list_events()]
    assert "similar_request_notified" not in audit_types


async def test_customer_notice_is_empty_for_editable_draft_source() -> None:
    app = create_app(
        Settings(environment="test", argon2_memory_cost=8_192, persistence_provider="memory")
    )
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        user = await login(client, "user@example.test")
        csrf_token = str(user["csrfToken"])
        # A visible, submitted match owned by the same customer would otherwise surface.
        await submitted_ticket(
            client,
            csrf_token,
            title="Vessel movements Gulf of Finland",
            question="What vessel movements are occurring around the Gulf of Finland?",
            region="Gulf of Finland",
            description="Track vessel movements near the Gulf of Finland.",
            output_format="movement report",
        )
        # The source ticket stays in an editable draft state (never submitted), so the
        # notice must not run: it is the replayable-probe surface we are closing.
        created = await client.post(
            "/api/v1/chat/messages",
            headers={"X-CSRF-Token": csrf_token},
            json={"message": "Boat traffic near St Petersburg."},
        )
        assert created.status_code == 201
        draft_id = created.json()["id"]
        await client.patch(
            f"/api/v1/tickets/{draft_id}/intake",
            headers={"X-CSRF-Token": csrf_token},
            json={
                "title": "Boat traffic near St Petersburg",
                "description": "Assess boat traffic near St Petersburg.",
                "operationalQuestion": "What boat traffic is near St Petersburg?",
                "areaOrRegion": "St Petersburg",
                "priority": "routine",
                "requiredOutputFormat": "traffic picture",
                "customerSuccessCriteria": "Identify activity requiring attention.",
            },
        )
        notice = await client.get(f"/api/v1/similar-requests/tickets/{draft_id}")

    assert notice.status_code == 200
    assert notice.json() == {"matches": []}
    audit_types = [event.event_type for event in app.state.auth_service.audit_log.list_events()]
    assert "similar_request_notified" not in audit_types


async def test_customer_join_adds_viewer_when_actor_owns_source_and_can_read_target() -> None:
    app = create_app(
        Settings(environment="test", argon2_memory_cost=8_192, persistence_provider="memory")
    )
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        colleague = await login(client, "colleague@example.test")
        target_id = await submitted_ticket(
            client,
            str(colleague["csrfToken"]),
            title="Vessel movements Gulf of Finland",
            question="What vessel movements are occurring around the Gulf of Finland?",
            region="Gulf of Finland",
            description="Track vessel movements near the Gulf of Finland.",
            output_format="movement report",
        )
        admin = await login(client, "admin@example.test")
        source_id = await submitted_ticket(
            client,
            str(admin["csrfToken"]),
            title="Boat traffic near St Petersburg",
            question="What boat traffic is near St Petersburg?",
            region="St Petersburg",
            description="Assess boat traffic near St Petersburg.",
            output_format="traffic picture",
        )
        joined = await client.post(
            f"/api/v1/similar-requests/tickets/{source_id}/join/{target_id}",
            headers={"X-CSRF-Token": str(admin["csrfToken"])},
        )

    target = app.state.ticket_services.tickets._repository.get(UUID(target_id))
    assert joined.status_code == 200
    assert target is not None
    assert any(
        collaborator.username == "admin@example.test" for collaborator in target.collaborators
    )
    assert _timeline_count(target, "similar_request_joined") == 1
    audit_types = [event.event_type for event in app.state.auth_service.audit_log.list_events()]
    assert "similar_request_joined" in audit_types
    assert "ticket_collaborator_added" in audit_types


async def test_manager_lists_and_links_similar_requests_idempotently() -> None:
    app = create_app(
        Settings(environment="test", argon2_memory_cost=8_192, persistence_provider="memory")
    )
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        user = await login(client, "user@example.test")
        source_id, target_id = await similar_ticket_pair(client, str(user["csrfToken"]))
        manager = await login(client, "rfa.manager@example.test")
        listed = await client.get(f"/api/v1/similar-requests/routing/{source_id}")
        linked = await client.post(
            f"/api/v1/similar-requests/routing/{source_id}/link/{target_id}",
            headers={"X-CSRF-Token": str(manager["csrfToken"])},
        )
        repeated = await client.post(
            f"/api/v1/similar-requests/routing/{source_id}/link/{target_id}",
            headers={"X-CSRF-Token": str(manager["csrfToken"])},
        )

    assert listed.status_code == 200
    assert listed.json()["matches"][0]["ticketId"] == target_id
    assert linked.status_code == 200
    assert linked.json()["matches"][0]["alreadyLinked"] is True
    assert repeated.status_code == 200

    source = app.state.ticket_services.tickets._repository.get(UUID(source_id))
    target = app.state.ticket_services.tickets._repository.get(UUID(target_id))
    assert source is not None
    assert target is not None
    assert target.ticket_id in source.related_ticket_ids
    assert source.ticket_id in target.related_ticket_ids
    assert _timeline_count(source, "related_ticket_linked") == 1
    assert _timeline_count(target, "related_ticket_linked") == 1
    audit_types = [event.event_type for event in app.state.auth_service.audit_log.list_events()]
    assert audit_types.count("tickets_linked") == 2


async def test_manager_link_failure_rolls_back_related_ticket(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = create_app(
        Settings(environment="test", argon2_memory_cost=8_192, persistence_provider="memory")
    )
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        user = await login(client, "user@example.test")
        source_id, target_id = await similar_ticket_pair(client, str(user["csrfToken"]))
        manager = await login(client, "rfa.manager@example.test")
        tickets = app.state.ticket_services.tickets
        original_save = tickets.save_system_update
        calls = 0

        def fail_second_save(ticket: TicketRecord) -> TicketRecord:
            nonlocal calls
            calls += 1
            if calls == 2:
                raise RuntimeError("simulated source save failure")
            return cast(TicketRecord, original_save(ticket))

        monkeypatch.setattr(tickets, "save_system_update", fail_second_save)
        with pytest.raises(RuntimeError, match="simulated source save failure"):
            await client.post(
                f"/api/v1/similar-requests/routing/{source_id}/link/{target_id}",
                headers={"X-CSRF-Token": str(manager["csrfToken"])},
            )

    source = app.state.ticket_services.tickets._repository.get(UUID(source_id))
    target = app.state.ticket_services.tickets._repository.get(UUID(target_id))
    assert source is not None
    assert target is not None
    assert source.related_ticket_ids == ()
    assert target.related_ticket_ids == ()
    assert _timeline_count(source, "related_ticket_linked") == 0
    assert _timeline_count(target, "related_ticket_linked") == 0


async def test_jioc_lists_similar_requests_for_a_routing_ticket() -> None:
    app = create_app(
        Settings(environment="test", argon2_memory_cost=8_192, persistence_provider="memory")
    )
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        user = await login(client, "user@example.test")
        source_id, target_id = await similar_ticket_pair(client, str(user["csrfToken"]))
        await login(client, "jioc.team@example.test")

        listed = await client.get(f"/api/v1/similar-requests/routing/{source_id}")

    assert listed.status_code == 200
    assert listed.json()["matches"][0]["ticketId"] == target_id


def _timeline_count(ticket: TicketRecord, event_type: str) -> int:
    return sum(1 for entry in ticket.timeline if entry.event_type == event_type)
