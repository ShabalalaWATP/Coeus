from types import SimpleNamespace
from typing import cast
from uuid import uuid4

import pytest
from fastapi import FastAPI

from coeus.api.identity_composition import IdentityComponents
from coeus.core.config import Settings
from coeus.domain.auth import RoleName, UserAccount
from coeus.main import _lifespan
from coeus.organisation_composition import (
    configure_organisation_shadow,
    reconcile_historical_task_ownership,
)
from coeus.repositories.teams import TeamRepository
from coeus.services.organisation_reconciliation import OrganisationReconciliationResult


def _identity(*users: UserAccount) -> IdentityComponents:
    directory = SimpleNamespace(list_users=lambda: users)
    return cast(IdentityComponents, SimpleNamespace(users=directory))


def _user(*, administrator: bool = True, active: bool = True) -> UserAccount:
    return UserAccount(
        uuid4(),
        "admin@example.test",
        "Synthetic Administrator",
        frozenset({RoleName.ADMINISTRATOR} if administrator else {RoleName.USER}),
        frozenset(),
        "not-a-real-hash",
        active,
        3,
    )


def test_disabled_mode_sets_stable_empty_state() -> None:
    app = FastAPI()
    configure_organisation_shadow(
        app,
        Settings(environment="test", persistence_provider="memory"),
        _identity(_user()),
        cast(TeamRepository, object()),
    )
    assert app.state.organisation_repository is None
    assert app.state.organisation_reconciliation_result is None
    assert app.state.organisation_engine is None
    assert app.state.team_task_ownership_repository is None
    assert app.state.organisation_administration is None
    assert app.state.task_ownership_reconciliation_result is None


@pytest.mark.asyncio
async def test_application_lifespan_disposes_the_organisation_engine() -> None:
    class Engine:
        disposed = False

        def dispose(self) -> None:
            self.disposed = True

    app = FastAPI()
    engine = Engine()
    app.state.organisation_engine = engine
    async with _lifespan(app):
        pass
    assert engine.disposed


def test_shadow_mode_wires_repository_and_reconciles(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = FastAPI()
    actor = _user()
    teams = SimpleNamespace(list_teams=lambda: ())
    result = OrganisationReconciliationResult(uuid4(), "a" * 64, 0, 0, 0)
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        "coeus.organisation_composition.create_engine", lambda *args, **kwargs: object()
    )

    def reconcile(self: object, **kwargs: object) -> OrganisationReconciliationResult:
        captured.update(kwargs)
        return result

    monkeypatch.setattr(
        "coeus.organisation_composition.OrganisationReconciliationService.reconcile",
        reconcile,
    )
    configure_organisation_shadow(
        app,
        Settings(environment="test", organisation_mode="shadow"),
        _identity(actor),
        cast(TeamRepository, teams),
    )
    assert app.state.organisation_repository is not None
    assert app.state.organisation_reconciliation_result == result
    assert app.state.organisation_engine is not None
    assert app.state.team_task_ownership_repository is not None
    assert captured["actor_user_id"] != actor.user_id


def test_active_mode_fails_closed_before_composing_authority(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = object()
    composed = False
    monkeypatch.setattr(
        "coeus.organisation_composition.create_engine", lambda *args, **kwargs: engine
    )

    def deny(self: object, candidate: object, revision: object) -> None:
        del self, candidate, revision
        raise ValueError("candidate is not eligible")

    def compose(*args: object) -> object:
        nonlocal composed
        composed = True
        return object()

    monkeypatch.setattr(
        "coeus.organisation_composition.CutoverActivationService."
        "assert_active_composition_eligible",
        deny,
    )
    monkeypatch.setattr("coeus.organisation_composition.build_organisation_administration", compose)
    with pytest.raises(ValueError, match="not eligible"):
        configure_organisation_shadow(
            FastAPI(),
            Settings(
                environment="test",
                organisation_mode="active",
                organisation_active_candidate_hash="a" * 64,
                organisation_cutover_source_revision="abcdef123456",
            ),
            _identity(),
            cast(TeamRepository, object()),
        )
    assert not composed


def test_management_mode_wires_commands_without_reconciling(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = FastAPI()
    engine = object()
    administration = SimpleNamespace(repository=object())
    monkeypatch.setattr(
        "coeus.organisation_composition.create_engine", lambda *args, **kwargs: engine
    )
    monkeypatch.setattr(
        "coeus.organisation_composition.build_organisation_administration",
        lambda *args: administration,
    )
    configure_organisation_shadow(
        app,
        Settings(environment="test", organisation_mode="management"),
        _identity(_user()),
        cast(TeamRepository, object()),
    )
    assert app.state.organisation_administration is administration
    assert app.state.organisation_repository is administration.repository
    assert app.state.organisation_engine is engine
    assert app.state.organisation_reconciliation_result is None
    assert app.state.cutover_activation_service is not None


def test_active_mode_composes_relational_administration_without_legacy_reconciliation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = FastAPI()
    engine = object()
    administration = SimpleNamespace(repository=object())
    eligibility: list[tuple[object, object]] = []
    monkeypatch.setattr(
        "coeus.organisation_composition.create_engine", lambda *args, **kwargs: engine
    )
    monkeypatch.setattr(
        "coeus.organisation_composition.build_organisation_administration",
        lambda *args: administration,
    )
    monkeypatch.setattr(
        "coeus.organisation_composition.CutoverActivationService."
        "assert_active_composition_eligible",
        lambda self, candidate, revision: eligibility.append((candidate, revision)),
    )
    settings = Settings(
        environment="test",
        organisation_mode="active",
        organisation_active_candidate_hash="a" * 64,
        organisation_cutover_source_revision="abcdef123456",
    )
    configure_organisation_shadow(app, settings, _identity(_user()), cast(TeamRepository, object()))
    assert eligibility == [("a" * 64, "abcdef123456")]
    assert app.state.organisation_administration is administration
    assert app.state.organisation_reconciliation_result is None


def test_management_startup_reconciles_historical_task_ownership() -> None:
    result = object()
    app = FastAPI()
    app.state.organisation_administration = SimpleNamespace(
        task_ownership_reconciliation=SimpleNamespace(reconcile=lambda: result)
    )
    reconcile_historical_task_ownership(
        app, Settings(environment="test", organisation_mode="management")
    )
    assert app.state.task_ownership_reconciliation_result is result
    reconcile_historical_task_ownership(app, Settings(environment="test"))


def test_management_startup_fails_closed_without_composition() -> None:
    app = FastAPI()
    app.state.organisation_administration = None
    with pytest.raises(RuntimeError, match="composition is unavailable"):
        reconcile_historical_task_ownership(
            app, Settings(environment="test", organisation_mode="management")
        )
