from collections.abc import Callable
from dataclasses import replace
from threading import Barrier, Thread
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from coeus.core.config import Settings
from coeus.core.errors import AppError
from coeus.domain.auth import UserAccount
from coeus.domain.teams import TeamKind
from coeus.domain.tickets import TicketRecord
from coeus.main import create_app
from rfi_search_helpers import login
from test_qc_api import _acg_id, _approval_payload, _submitted_qc_ticket


@pytest.mark.asyncio
async def test_qc_claim_hides_detail_and_allows_only_the_assigned_reviewer() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    second_username = _add_second_qc_reviewer(app)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        ticket_id = await _submitted_qc_ticket(client, app, "Assigned reviewer product")
        first = await login(client, "qc.manager@example.test")
        queue_before = await client.get("/api/v1/qc/queue")
        hidden_before = await client.get(f"/api/v1/qc/products/{ticket_id}")
        claimed = await client.post(
            f"/api/v1/qc/products/{ticket_id}/claim",
            headers={"X-CSRF-Token": str(first["csrfToken"])},
        )
        claimed_again = await client.post(
            f"/api/v1/qc/products/{ticket_id}/claim",
            headers={"X-CSRF-Token": str(first["csrfToken"])},
        )

        second = await login(client, second_username)
        second_queue = await client.get("/api/v1/qc/queue")
        second_detail = await client.get(f"/api/v1/qc/products/{ticket_id}")
        second_claim = await client.post(
            f"/api/v1/qc/products/{ticket_id}/claim",
            headers={"X-CSRF-Token": str(second["csrfToken"])},
        )
        second_reject = await client.post(
            f"/api/v1/qc/products/{ticket_id}/reject",
            headers={"X-CSRF-Token": str(second["csrfToken"])},
            json={"reason": "Should not be accepted."},
        )
        second_approve = await client.post(
            f"/api/v1/qc/products/{ticket_id}/approve",
            headers={"X-CSRF-Token": str(second["csrfToken"])},
            json=_approval_payload(_acg_id(app, "ACG-EU-CYBER")),
        )

    item = queue_before.json()["items"][0]
    assert queue_before.json()["products"] == []
    assert item["claimStatus"] == "available"
    assert set(item) == {"ticketId", "reference", "state", "claimStatus"}
    assert hidden_before.status_code == 404
    assert claimed.status_code == 200
    assert claimed.json()["latestDraft"]["title"] == "Assigned reviewer product"
    assert claimed_again.status_code == 200
    assert second_queue.json()["products"] == []
    assert second_queue.json()["items"][0]["claimStatus"] == "claimed"
    assert second_detail.status_code == 404
    assert second_claim.status_code == 409
    assert second_claim.json()["error"]["code"] == "qc_already_claimed"
    assert second_reject.status_code == 409
    assert second_approve.status_code == 409


@pytest.mark.asyncio
async def test_qc_claim_release_allows_a_deliberate_handoff() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    second_username = _add_second_qc_reviewer(app)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        ticket_id = await _submitted_qc_ticket(client, app, "QC handoff product")
        first = await login(client, "qc.manager@example.test")
        claimed = await client.post(
            f"/api/v1/qc/products/{ticket_id}/claim",
            headers={"X-CSRF-Token": str(first["csrfToken"])},
        )
        released = await client.delete(
            f"/api/v1/qc/products/{ticket_id}/claim",
            headers={"X-CSRF-Token": str(first["csrfToken"])},
        )
        hidden_after_release = await client.get(f"/api/v1/qc/products/{ticket_id}")
        second = await login(client, second_username)
        reclaimed = await client.post(
            f"/api/v1/qc/products/{ticket_id}/claim",
            headers={"X-CSRF-Token": str(second["csrfToken"])},
        )

    assert claimed.status_code == 200
    assert released.status_code == 204
    assert hidden_after_release.status_code == 404
    assert reclaimed.status_code == 200
    ticket = app.state.ticket_services.tickets._repository.get(UUID(ticket_id))
    assert ticket is not None
    second_user = app.state.access_services.repository.get_user_by_username(second_username)
    assert second_user is not None
    assert ticket.qc_reviewer_user_id == second_user.user_id
    assert [entry.event_type for entry in ticket.timeline[-3:]] == [
        "qc_agent_preflight_completed",
        "qc_claim_released",
        "qc_claimed",
    ]


@pytest.mark.asyncio
async def test_competing_memory_claims_have_one_winner_and_one_audit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    second_username = _add_second_qc_reviewer(app)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        ticket_id = await _submitted_qc_ticket(client, app, "Concurrent claim product")
    users = app.state.access_services.repository
    first = users.get_user_by_username("qc.manager@example.test")
    second = users.get_user_by_username(second_username)
    assert first is not None and second is not None
    repository = app.state.ticket_services.tickets._repository
    original = repository.save_if_current_with_confirmation
    barrier = Barrier(2)

    def coordinated(
        expected: TicketRecord,
        proposed: TicketRecord,
        confirm: Callable[[], object],
    ) -> bool:
        barrier.wait(timeout=5)
        return bool(original(expected, proposed, confirm))

    monkeypatch.setattr(repository, "save_if_current_with_confirmation", coordinated)
    results: list[object] = []

    def claim(actor: UserAccount) -> None:
        try:
            results.append(app.state.quality_control_service.claim(actor, UUID(ticket_id)))
        except AppError as exc:
            results.append(exc)

    threads = [Thread(target=claim, args=(actor,)) for actor in (first, second)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    assert all(not thread.is_alive() for thread in threads)
    errors = [result for result in results if isinstance(result, AppError)]
    assert len(errors) == 1 and errors[0].code == "qc_already_claimed"
    current = repository.get(UUID(ticket_id))
    assert current is not None
    assert current.qc_reviewer_user_id in {first.user_id, second.user_id}
    claim_events = [
        event
        for event in app.state.quality_control_service._audit_log.list_events()
        if event.event_type == "qc_claimed"
    ]
    assert len(claim_events) == 1


@pytest.mark.asyncio
async def test_claim_audit_failure_rolls_back_assignment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        ticket_id = await _submitted_qc_ticket(client, app, "Claim rollback product")
    actor = app.state.access_services.repository.get_user_by_username("qc.manager@example.test")
    assert actor is not None
    audit_log = app.state.quality_control_service._audit_log
    monkeypatch.setattr(
        audit_log,
        "record_many",
        lambda *_args: (_ for _ in ()).throw(RuntimeError("claim audit failed")),
    )

    with pytest.raises(RuntimeError, match="claim audit failed"):
        app.state.quality_control_service.claim(actor, UUID(ticket_id))

    current = app.state.ticket_services.tickets._repository.get(UUID(ticket_id))
    assert current is not None
    assert current.qc_reviewer_user_id is None
    assert current.qc_claimed_at is None


@pytest.mark.asyncio
async def test_qc_claim_enforces_author_and_active_analyst_separation_of_duties() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        authored_id = await _submitted_qc_ticket(client, app, "Self-authored QC product")
        assigned_id = await _submitted_qc_ticket(client, app, "Self-assigned QC product")
        session = await login(client, "qc.manager@example.test")
        actor = app.state.access_services.repository.get_user_by_username("qc.manager@example.test")
        assert actor is not None
        repository = app.state.ticket_services.tickets._repository
        authored = repository.get(UUID(authored_id))
        assigned = repository.get(UUID(assigned_id))
        assert authored is not None and assigned is not None
        repository.save(
            replace(
                authored,
                draft_products=(
                    replace(authored.draft_products[0], created_by_user_id=actor.user_id),
                ),
            )
        )
        repository.save(
            replace(
                assigned,
                analyst_assignments=(
                    replace(
                        assigned.analyst_assignments[0],
                        analyst_user_id=actor.user_id,
                        active=True,
                    ),
                ),
            )
        )
        authored_claim = await client.post(
            f"/api/v1/qc/products/{authored_id}/claim",
            headers={"X-CSRF-Token": str(session["csrfToken"])},
        )
        assigned_claim = await client.post(
            f"/api/v1/qc/products/{assigned_id}/claim",
            headers={"X-CSRF-Token": str(session["csrfToken"])},
        )

    assert authored_claim.status_code == 403
    assert authored_claim.json()["error"]["code"] == "separation_of_duties"
    assert assigned_claim.status_code == 403
    assert assigned_claim.json()["error"]["code"] == "separation_of_duties"


def test_qc_queue_requires_an_active_qc_team_member() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    actor = app.state.access_services.repository.get_user_by_username("qc.manager@example.test")
    assert actor is not None
    team = next(team for team in app.state.team_repository.list_teams() if team.kind == TeamKind.QC)
    app.state.team_repository.save_team(
        replace(
            team,
            manager_user_ids=tuple(
                user_id for user_id in team.manager_user_ids if user_id != actor.user_id
            ),
            member_user_ids=tuple(
                user_id for user_id in team.member_user_ids if user_id != actor.user_id
            ),
        )
    )

    with pytest.raises(AppError, match="Permission denied") as removed:
        app.state.quality_control_service.queue(actor)
    with pytest.raises(AppError, match="Permission denied") as disabled:
        app.state.quality_control_service.queue(replace(actor, is_active=False))

    assert removed.value.code == "forbidden"
    assert disabled.value.code == "forbidden"


def _add_second_qc_reviewer(app: FastAPI) -> str:
    users = app.state.access_services.repository
    template = users.get_user_by_username("qc.manager@example.test")
    assert template is not None
    username = "qc.second@example.test"
    reviewer = replace(
        template,
        user_id=uuid4(),
        username=username,
        display_name="Second QC Manager",
    )
    users._users.save(reviewer)
    team = next(team for team in app.state.team_repository.list_teams() if team.kind == TeamKind.QC)
    app.state.team_repository.save_team(
        replace(team, manager_user_ids=(*team.manager_user_ids, reviewer.user_id))
    )
    return username
