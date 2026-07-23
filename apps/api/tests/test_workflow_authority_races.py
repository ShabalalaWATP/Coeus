"""Commit-time authority regressions for interactive workflow writes."""

from collections.abc import Callable
from dataclasses import replace
from typing import Any
from uuid import UUID

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

import coeus.services.rfi_search as rfi_search_module
from coeus.core.config import Settings
from coeus.domain.access import ProductStatus
from coeus.domain.enums import TicketState
from coeus.domain.teams import TeamKind
from coeus.domain.tickets import TicketRecord
from coeus.main import create_app
from rfi_search_helpers import ensure_search_index_ready, login, submitted_ticket
from test_qc_api import _acg_id, _approval_payload, _submitted_qc_ticket
from test_similar_requests_api import similar_ticket_pair
from ticket_api_helpers import stored_ticket


def _app() -> FastAPI:
    return create_app(
        Settings(
            environment="test",
            argon2_memory_cost=8_192,
            automatic_request_discovery_enabled=False,
        )
    )


def _disable(app: FastAPI, username: str) -> None:
    users = app.state.access_services.repository
    actor = users.get_user_by_username(username)
    admin = users.get_user_by_username("admin@example.test")
    assert actor is not None and admin is not None
    app.state.user_admin_service.set_active(admin, actor.user_id, False)


@pytest.mark.asyncio
@pytest.mark.parametrize("revocation", ["account", "session"])
@pytest.mark.parametrize("existing_ticket", [False, True], ids=["create", "update"])
async def test_chat_commit_rejects_authority_revoked_during_reply(
    monkeypatch: pytest.MonkeyPatch,
    existing_ticket: bool,
    revocation: str,
) -> None:
    app = _app()
    conversations = app.state.ticket_services.conversations
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        session = await login(client, "user@example.test")
        csrf = str(session["csrfToken"])
        ticket_id: str | None = None
        before: TicketRecord | None = None
        if existing_ticket:
            created = await client.post(
                "/api/v1/chat/messages",
                headers={"X-CSRF-Token": csrf},
                json={"message": "Synthetic initial request."},
            )
            assert created.status_code == 201
            ticket_id = str(created.json()["id"])
            before = stored_ticket(app, ticket_id)

        original = conversations._reply_and_status
        audit_before = _audit_count(app, "ticket_chat_message_received")

        def revoke_during_reply(*args: Any, **kwargs: Any) -> Any:
            if revocation == "account":
                _disable(app, "user@example.test")
            else:
                assert _revoke_sessions(app, "user@example.test") == 1
            return original(*args, **kwargs)

        monkeypatch.setattr(conversations, "_reply_and_status", revoke_during_reply)
        response = await client.post(
            "/api/v1/chat/messages",
            headers={"X-CSRF-Token": csrf},
            json={"message": "Synthetic authority-race request.", "ticketId": ticket_id},
        )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"
    tickets = app.state.ticket_services.tickets._repository.list_tickets()
    if before is None:
        assert tickets == ()
    else:
        assert stored_ticket(app, str(before.ticket_id)) == before
    assert _audit_count(app, "ticket_chat_message_received") == audit_before


@pytest.mark.asyncio
@pytest.mark.parametrize("revocation", ["account", "session"])
async def test_active_work_commit_rejects_account_changed_during_discovery(
    monkeypatch: pytest.MonkeyPatch,
    revocation: str,
) -> None:
    app = _app()
    similar = app.state.similar_request_service
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        session = await login(client, "user@example.test")
        csrf = str(session["csrfToken"])
        source_id, _target_id = await similar_ticket_pair(client, csrf)
        source = stored_ticket(app, source_id)
        pending = app.state.ticket_services.tickets.save_system_update(
            replace(source, state=TicketState.NEW_TASKING_CONSENT)
        )
        original: Callable[..., Any] = similar.customer_matches
        audit_before = _audit_count(app, "similar_request_notified")

        def revoke_during_discovery(*args: Any, **kwargs: Any) -> Any:
            if revocation == "account":
                _disable(app, "user@example.test")
            else:
                assert _revoke_sessions(app, "user@example.test") == 1
            return original(*args, **kwargs)

        monkeypatch.setattr(similar, "customer_matches", revoke_during_discovery)
        response = await client.post(
            f"/api/v1/similar-requests/tickets/{source_id}/retry",
            headers={"X-CSRF-Token": csrf},
        )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"
    assert stored_ticket(app, source_id) == pending
    assert _audit_count(app, "similar_request_notified") == audit_before


@pytest.mark.asyncio
@pytest.mark.parametrize("revocation", ["account", "session", "acg"])
async def test_rfi_commit_rejects_permission_revoked_during_retrieval(
    monkeypatch: pytest.MonkeyPatch,
    revocation: str,
) -> None:
    app = _app()
    embeddings = app.state.rfi_search_service._embeddings
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        session = await login(client, "user@example.test")
        csrf = str(session["csrfToken"])
        ticket_id = await submitted_ticket(client, csrf)
        before = stored_ticket(app, ticket_id)
        original = embeddings.embed_cached
        access = app.state.access_services.repository
        actor = access.get_user_by_username("user@example.test")
        assert actor is not None
        acg_id = next(iter(access.active_acg_ids_for_user(actor.user_id)))
        revoked = False

        def revoke_during_retrieval(*args: Any, **kwargs: Any) -> Any:
            nonlocal revoked
            if revoked:
                return original(*args, **kwargs)
            revoked = True
            if revocation == "account":
                _disable(app, "user@example.test")
            elif revocation == "session":
                assert _revoke_sessions(app, "user@example.test") == 1
            else:
                access.remove_membership(acg_id, actor.user_id)
            return original(*args, **kwargs)

        monkeypatch.setattr(embeddings, "embed_cached", revoke_during_retrieval)
        response = await client.post(
            f"/api/v1/rfi-search/{ticket_id}/run",
            headers={"X-CSRF-Token": csrf},
        )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"
    assert stored_ticket(app, ticket_id) == before


@pytest.mark.asyncio
async def test_rfi_commit_rejects_restricted_non_offered_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _app()
    ensure_search_index_ready(app)
    repository = app.state.store_services.repository
    original = rfi_search_module.ranked_additive_offers
    audit_before = _audit_count(app, "rfi_search_completed")
    restricted_product_id: UUID | None = None

    def restrict_during_ranking(*args: Any, **kwargs: Any) -> tuple[Any, ...]:
        nonlocal restricted_product_id
        retrieval = args[0]
        offers = original(*args, **kwargs)
        assert retrieval.grounded.evidence
        restricted_product_id = retrieval.grounded.evidence[0].product_id
        product = repository.get_product(restricted_product_id)
        assert product is not None
        repository.save_product(
            replace(
                product,
                metadata=replace(product.metadata, status=ProductStatus.ARCHIVED),
            )
        )
        return tuple(offer for offer in offers if offer.product_id != restricted_product_id)

    monkeypatch.setattr(
        rfi_search_module,
        "ranked_additive_offers",
        restrict_during_ranking,
    )
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        session = await login(client, "user@example.test")
        csrf = str(session["csrfToken"])
        ticket_id = await submitted_ticket(client, csrf)
        before = stored_ticket(app, ticket_id)
        response = await client.post(
            f"/api/v1/rfi-search/{ticket_id}/run",
            headers={"X-CSRF-Token": csrf},
        )

    assert restricted_product_id is not None
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"
    assert stored_ticket(app, ticket_id) == before
    assert _audit_count(app, "rfi_search_completed") == audit_before


@pytest.mark.asyncio
@pytest.mark.parametrize("revocation", ["account", "session", "qc_team", "release_acg"])
async def test_qc_commit_rejects_permission_revoked_during_indexing(
    monkeypatch: pytest.MonkeyPatch,
    revocation: str,
) -> None:
    app = _app()
    qc = app.state.quality_control_service
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        ticket_id = await _submitted_qc_ticket(client, app, "QC authority race product")
        before = stored_ticket(app, ticket_id)
        original = qc._indexing.index_product
        original_can_read = qc._release._store.details.can_read_product
        access = app.state.access_services.repository
        actor = access.get_user_by_username("qc.manager@example.test")
        assert actor is not None

        def revoke_during_indexing(*args: Any, **kwargs: Any) -> Any:
            if revocation == "account":
                _disable(app, "qc.manager@example.test")
            elif revocation == "session":
                assert _revoke_sessions(app, "qc.manager@example.test") == 1
            elif revocation == "qc_team":
                team = next(
                    team
                    for team in app.state.team_repository.list_teams()
                    if team.kind is TeamKind.QC
                )
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
            return original(*args, **kwargs)

        def revoke_after_release_preflight(*args: Any, **kwargs: Any) -> bool:
            allowed = original_can_read(*args, **kwargs)
            acg_id = _acg_id(app, "ACG-EU-CYBER")
            acg = access.get_acg(UUID(acg_id))
            assert acg is not None
            access.save_acg(replace(acg, is_active=False))
            return allowed

        monkeypatch.setattr(qc._indexing, "index_product", revoke_during_indexing)
        if revocation == "release_acg":
            monkeypatch.setattr(
                qc._release._store.details,
                "can_read_product",
                revoke_after_release_preflight,
            )
        session = await login(client, "qc.manager@example.test")
        response = await client.post(
            f"/api/v1/qc/products/{ticket_id}/approve",
            headers={"X-CSRF-Token": str(session["csrfToken"])},
            json=_approval_payload(_acg_id(app, "ACG-EU-CYBER")),
        )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"
    current = stored_ticket(app, ticket_id)
    assert current.state == TicketState.QC_REVIEW
    assert current.qc_decisions == before.qc_decisions
    assert current.product_index_records == before.product_index_records
    assert current.disseminations == before.disseminations
    assert not any(
        product.metadata.title == "QC authority race product"
        for product in app.state.store_services.repository.list_products()
    )


def _audit_count(app: FastAPI, event_type: str) -> int:
    return sum(
        event.event_type == event_type for event in app.state.auth_service.audit_log.list_events()
    )


def _revoke_sessions(app: FastAPI, username: str) -> int:
    user = app.state.access_services.repository.get_user_by_username(username)
    assert user is not None
    return len(app.state.auth_service._sessions.delete_for_user(user.user_id))
