"""Regression coverage for commit-time product-submission authority."""

import asyncio
import json
import threading
from dataclasses import replace
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient

import coeus.services.product_submissions as submissions_module
from coeus.core.config import Settings
from coeus.core.errors import AppError
from coeus.domain.enums import TicketState
from coeus.domain.tickets import IntakeDetails, TicketRecord
from coeus.main import create_app
from rfi_search_helpers import login
from test_external_product_workflow import _assigned_ticket, _docx, _metadata


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("revocation", "expected_code"),
    (("acg", "acg_not_authorised"), ("account", "forbidden")),
)
async def test_authority_revocation_fences_inflight_submission_commit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    revocation: str,
    expected_code: str,
) -> None:
    app = _app(tmp_path)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        ticket_id = await _assigned_ticket(client, app)
        actor, acg_id = _analyst_and_acg(app)
        ticket_before = app.state.ticket_services.tickets._repository.get(UUID(ticket_id))
        assert ticket_before is not None
        audit_before = _submission_audit_count(app)
        parser_entered = threading.Event()
        parser_release = threading.Event()
        original = submissions_module.process_product_file

        def paused_processor(*args: Any, **kwargs: Any) -> Any:
            parser_entered.set()
            assert parser_release.wait(timeout=15)
            return original(*args, **kwargs)

        monkeypatch.setattr(submissions_module, "process_product_file", paused_processor)
        result: dict[str, Any] = {}
        failure: list[BaseException] = []
        worker = threading.Thread(
            target=_upload_in_thread,
            args=(app, ticket_id, acg_id, result, failure),
            daemon=True,
        )
        worker.start()
        assert parser_entered.wait(timeout=15)
        admin = await login(client, "admin@example.test")
        if revocation == "acg":
            revoked = await client.delete(
                f"/api/v1/acgs/{acg_id}/members/{actor.user_id}",
                headers={"X-CSRF-Token": str(admin["csrfToken"])},
            )
            assert revoked.status_code == 204
        else:
            revoked = await client.put(
                f"/api/v1/admin/users/{actor.user_id}/status",
                headers={"X-CSRF-Token": str(admin["csrfToken"])},
                json={"isActive": False},
            )
            assert revoked.status_code == 200
        parser_release.set()
        worker.join(timeout=20)

    assert not worker.is_alive()
    assert failure == []
    assert result["status_code"] == 403
    assert result["body"]["error"]["code"] == expected_code
    assert app.state.ticket_services.tickets._repository.get(UUID(ticket_id)) == ticket_before
    assert _submission_audit_count(app) == audit_before
    assert not any((tmp_path / "objects").rglob("*.*"))


@pytest.mark.asyncio
async def test_current_authority_preserves_valid_submission(tmp_path: Path) -> None:
    app = _app(tmp_path)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        ticket_id = await _assigned_ticket(client, app)
        _actor, acg_id = _analyst_and_acg(app)
        response = await _upload(client, ticket_id, acg_id)

    assert response.status_code == 201
    ticket = app.state.ticket_services.tickets._repository.get(UUID(ticket_id))
    assert ticket is not None and len(ticket.draft_products) == 1
    asset = ticket.draft_products[0].assets[0]
    assert app.state.object_storage.exists(asset.object_key)
    assert _submission_audit_count(app) == 1


def test_submission_and_ticket_save_follow_one_lock_order(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _app(tmp_path)
    repository = app.state.ticket_services.tickets._repository
    actor, acg_id = _analyst_and_acg(app)
    ticket = TicketRecord(
        ticket_id=uuid4(),
        reference=repository.next_reference(),
        requester_user_id=actor.user_id,
        state=TicketState.ANALYST_IN_PROGRESS,
        intake=IntakeDetails(title="Synthetic lock-order regression"),
    )
    repository.save(ticket)
    winner = replace(ticket, manager_approved_manifest_hash="ordinary-ticket-save")
    loser = replace(ticket, manager_approved_manifest_hash="guarded-submission")
    ordinary_holds_ticket = threading.Event()
    release_ordinary = threading.Event()
    submission_waiting = threading.Event()
    ordinary_errors: list[BaseException] = []
    submission_errors: list[BaseException] = []
    original_persist = repository._persist
    original_guarded = repository.save_if_current_with_guarded_confirmation

    def paused_persist(changed: Any = None) -> None:
        if threading.current_thread() is ordinary:
            ordinary_holds_ticket.set()
            if not release_ordinary.wait(timeout=10):
                raise TimeoutError("ordinary ticket save was not released")
        original_persist(changed)

    def observed_guarded(*args: Any, **kwargs: Any) -> bool:
        submission_waiting.set()
        return original_guarded(*args, **kwargs)

    monkeypatch.setattr(repository, "_persist", paused_persist)
    monkeypatch.setattr(repository, "save_if_current_with_guarded_confirmation", observed_guarded)

    def save_ordinary_ticket() -> None:
        try:
            repository.save(winner)
        except BaseException as exc:
            ordinary_errors.append(exc)

    def save_submission() -> None:
        try:
            app.state.ticket_services.mutations.save_submission_if_authorised(
                ticket,
                loser,
                actor,
                {"ticket_id": str(ticket.ticket_id)},
                frozenset({acg_id}),
                app.state.state_store,
            )
        except BaseException as exc:
            submission_errors.append(exc)

    ordinary = threading.Thread(target=save_ordinary_ticket, daemon=True)
    submission = threading.Thread(target=save_submission, daemon=True)
    ordinary.start()
    assert ordinary_holds_ticket.wait(timeout=10)
    submission.start()
    try:
        assert submission_waiting.wait(timeout=10)
    finally:
        release_ordinary.set()
    ordinary.join(timeout=10)
    submission.join(timeout=10)

    assert not ordinary.is_alive() and not submission.is_alive()
    assert ordinary_errors == []
    assert len(submission_errors) == 1
    assert isinstance(submission_errors[0], AppError)
    assert submission_errors[0].code == "ticket_changed"
    assert repository.get(ticket.ticket_id) == winner
    assert _submission_audit_count(app) == 0


def _app(tmp_path: Path) -> Any:
    return create_app(
        Settings(
            environment="test",
            argon2_memory_cost=8_192,
            local_object_storage_path=str(tmp_path / "objects"),
            persistence_provider="memory",
            seed_demo_content=False,
        )
    )


def _analyst_and_acg(app: Any) -> tuple[Any, UUID]:
    actor = app.state.access_services.repository.get_user_by_username("analyst@example.test")
    assert actor is not None
    acg_id = next(
        acg.acg_id
        for acg in app.state.access_services.repository.list_acgs()
        if acg.code == "ACG-EU-CYBER"
    )
    return actor, acg_id


async def _upload(client: AsyncClient, ticket_id: str, acg_id: UUID) -> Any:
    analyst = await login(client, "analyst@example.test")
    return await client.post(
        f"/api/v1/analyst/tasks/{ticket_id}/submissions/upload",
        headers={"X-CSRF-Token": str(analyst["csrfToken"])},
        files={
            "asset": (
                "authority-race.docx",
                _docx("MOCK DATA ONLY. Commit-time authority regression."),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ),
            "metadata": (None, json.dumps(_metadata(str(acg_id))), "application/json"),
        },
    )


def _upload_in_thread(
    app: Any,
    ticket_id: str,
    acg_id: UUID,
    result: dict[str, Any],
    failure: list[BaseException],
) -> None:
    async def run() -> None:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            response = await _upload(client, ticket_id, acg_id)
            result.update(status_code=response.status_code, body=response.json())

    try:
        asyncio.run(run())
    except BaseException as exc:
        failure.append(exc)


def _submission_audit_count(app: Any) -> int:
    return sum(
        event.event_type == "product_submission_uploaded"
        for event in app.state.auth_service.audit_log.list_events()
    )
