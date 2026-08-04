"""Policy and contract tests for the local-only synthetic organisation fixture."""

from dataclasses import replace
from types import SimpleNamespace
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from coeus.api.organisation_dependencies import get_organisation_administration
from coeus.core.config import Settings
from coeus.core.permissions import Permission
from coeus.domain.auth import UserAccount
from coeus.domain.synthetic_organisation_fixture import (
    SyntheticFixtureCommand,
    SyntheticFixtureCounts,
    SyntheticFixtureFinding,
    SyntheticFixturePreview,
    SyntheticFixtureResult,
    SyntheticFixtureUnavailable,
    fixture_preview_hash,
)
from coeus.main import create_app
from coeus.repositories.auth_seed import seed_user_specs
from coeus.services.synthetic_organisation_fixture import (
    SyntheticOrganisationFixtureService,
)
from rfi_search_helpers import login


class _Store:
    def __init__(self) -> None:
        self.command: SyntheticFixtureCommand | None = None
        self.users = ()
        self.preview_value = SyntheticFixturePreview(
            "synthetic-organisation-v2",
            "a" * 64,
            SyntheticFixtureCounts(25, 7, 53, 24, 107, 21, 48, 8, 24, 24, 48),
            SyntheticFixtureCounts(),
            (),
        )

    def preview(self, actor_user_id, users):  # type: ignore[no-untyped-def]
        del actor_user_id
        self.users = users
        return self.preview_value

    def apply(self, command, users):  # type: ignore[no-untyped-def]
        self.command = command
        self.users = users
        return SyntheticFixtureResult(
            command.command_id,
            "synthetic-organisation-v2",
            self.preview_value.creates,
        )

    def reconcile(self, command, users):  # type: ignore[no-untyped-def]
        result = self.apply(command, users)
        return replace(result, reconciled_rows=1)


class _Users:
    def __init__(self, actor: UserAccount, *, current: bool = True) -> None:
        self.actor = actor
        self.current = current
        self.seed = {
            spec.username.casefold(): replace(
                actor,
                user_id=uuid4(),
                username=spec.username,
                display_name=spec.display_name,
                is_active=spec.username != "disabled@example.test",
            )
            for spec in seed_user_specs()
        }

    def get_seed_by_canonical_username(self, username: str):  # type: ignore[no-untyped-def]
        return self.seed.get(username.casefold())

    def confirm_current_authority(self, actor, permissions, confirm):  # type: ignore[no-untyped-def]
        if (
            not self.current
            or actor != self.actor
            or Permission.SYSTEM_CONFIGURE not in permissions
        ):
            return False
        confirm()
        return True


def _actor() -> UserAccount:
    return UserAccount(
        uuid4(),
        "admin@example.test",
        "Synthetic Administrator",
        frozenset(),
        frozenset({Permission.SYSTEM_CONFIGURE}),
        "not-used",
        True,
        3,
    )


def test_fixture_hash_is_deterministic_and_actor_bound() -> None:
    actor_id = uuid4()
    first = fixture_preview_hash(actor_id, "v2", [("row", 1)])
    assert first == fixture_preview_hash(actor_id, "v2", [("row", 1)])
    assert first != fixture_preview_hash(uuid4(), "v2", [("row", 1)])
    assert first != fixture_preview_hash(actor_id, "v2", [("row", 2)])
    assert SyntheticFixtureCounts(1, 2, 3, 4, 5).total == 15


def test_fixture_service_resolves_all_canonical_users_and_confirms_authority() -> None:
    actor = _actor()
    users = _Users(actor)
    store = _Store()
    service = SyntheticOrganisationFixtureService(store, users, enabled=True)  # type: ignore[arg-type]
    preview = service.preview(actor)
    command = SyntheticFixtureCommand(uuid4(), "fixture-1", actor.user_id, preview.preview_hash)
    result = service.apply(command, actor, reauthenticated=True)
    assert result.created.memberships == 53
    assert len(store.users) == 53
    assert store.command == command

    reconcile_command = SyntheticFixtureCommand(
        uuid4(), "fixture-reconcile-1", actor.user_id, preview.preview_hash
    )
    reconciled = service.reconcile(reconcile_command, actor, reauthenticated=True)
    assert reconciled.reconciled_rows == 1


def test_fixture_service_is_fail_closed() -> None:
    actor = _actor()
    users = _Users(actor)
    store = _Store()
    disabled = SyntheticOrganisationFixtureService(store, users, enabled=False)  # type: ignore[arg-type]
    with pytest.raises(SyntheticFixtureUnavailable, match="disabled"):
        disabled.preview(actor)
    service = SyntheticOrganisationFixtureService(store, users, enabled=True)  # type: ignore[arg-type]
    command = SyntheticFixtureCommand(uuid4(), "fixture-2", actor.user_id, "a" * 64)
    with pytest.raises(SyntheticFixtureUnavailable, match="authentication"):
        service.apply(command, actor, reauthenticated=False)
    with pytest.raises(SyntheticFixtureUnavailable, match="authority changed"):
        SyntheticOrganisationFixtureService(  # type: ignore[arg-type]
            store, _Users(actor, current=False), enabled=True
        ).apply(command, actor, reauthenticated=True)
    denied = replace(actor, is_active=False)
    with pytest.raises(SyntheticFixtureUnavailable, match="authority"):
        service.preview(denied)


class _FixtureApi:
    def __init__(self) -> None:
        self.applied: SyntheticFixtureCommand | None = None
        self.reconciled: SyntheticFixtureCommand | None = None

    def preview(self, actor):  # type: ignore[no-untyped-def]
        del actor
        return SyntheticFixturePreview(
            "synthetic-organisation-v2",
            "b" * 64,
            SyntheticFixtureCounts(25, 7, 53, 24, 107, 21, 48, 8, 24, 24, 48),
            SyntheticFixtureCounts(),
            (
                SyntheticFixtureFinding(
                    "foreign_root", "unit", "di", "A different active root exists."
                ),
            ),
        )

    def apply(self, command, actor, *, reauthenticated):  # type: ignore[no-untyped-def]
        del actor, reauthenticated
        self.applied = command
        return SyntheticFixtureResult(
            command.command_id,
            "synthetic-organisation-v2",
            SyntheticFixtureCounts(25, 7, 53, 24, 107, 21, 48, 8, 24, 24, 48),
        )

    def reconcile(self, command, actor, *, reauthenticated):  # type: ignore[no-untyped-def]
        del actor, reauthenticated
        self.reconciled = command
        return SyntheticFixtureResult(
            command.command_id,
            "synthetic-organisation-v2",
            SyntheticFixtureCounts(),
            reconciled_rows=1,
        )


def _api_app():  # type: ignore[no-untyped-def]
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    fixture = _FixtureApi()
    administration = SimpleNamespace(synthetic_fixture=fixture)
    app.dependency_overrides[get_organisation_administration] = lambda: administration
    return app, fixture


@pytest.mark.asyncio
async def test_fixture_api_requires_csrf_and_password_and_never_accepts_actor_ids() -> None:
    app, fixture = _api_app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        session = await login(client, "admin@example.test")
        assert (
            await client.post("/api/v1/admin/organisation/synthetic-fixture-preview")
        ).status_code == 403
        preview = await client.post(
            "/api/v1/admin/organisation/synthetic-fixture-preview",
            headers={"X-CSRF-Token": session["csrfToken"]},
        )
        assert preview.status_code == 200
        assert preview.json()["canApply"] is False
        assert preview.json()["creates"]["total"] == 389
        payload = {
            "commandId": str(uuid4()),
            "idempotencyKey": "synthetic-fixture-api-1",
            "previewHash": "b" * 64,
            "currentPassword": "wrong-password",
            "actorUserId": str(uuid4()),
        }
        wrong = await client.post(
            "/api/v1/admin/organisation/synthetic-fixture-commands",
            headers={"X-CSRF-Token": session["csrfToken"]},
            json={key: value for key, value in payload.items() if key != "actorUserId"},
        )
        assert wrong.status_code == 401
        injected = await client.post(
            "/api/v1/admin/organisation/synthetic-fixture-commands",
            headers={"X-CSRF-Token": session["csrfToken"]},
            json={**payload, "currentPassword": "CoeusLocal1!"},
        )
        assert injected.status_code == 422
        applied = await client.post(
            "/api/v1/admin/organisation/synthetic-fixture-commands",
            headers={"X-CSRF-Token": session["csrfToken"]},
            json={
                key: value
                for key, value in {**payload, "currentPassword": "CoeusLocal1!"}.items()
                if key != "actorUserId"
            },
        )
        reconciled = await client.post(
            "/api/v1/admin/organisation/synthetic-fixture-reconcile-commands",
            headers={"X-CSRF-Token": session["csrfToken"]},
            json={
                "commandId": str(uuid4()),
                "idempotencyKey": "synthetic-fixture-api-reconcile-1",
                "previewHash": "b" * 64,
                "currentPassword": "CoeusLocal1!",
            },
        )
    assert applied.status_code == 200
    assert reconciled.status_code == 200
    assert reconciled.json()["reconciledRows"] == 1
    administrator = app.state.access_services.repository.get_user_by_username("admin@example.test")
    assert administrator is not None
    assert fixture.applied is not None
    assert fixture.applied.actor_user_id == administrator.user_id
    assert fixture.reconciled is not None
    assert fixture.reconciled.actor_user_id == administrator.user_id
    assert str(administrator.user_id) != payload["actorUserId"]
