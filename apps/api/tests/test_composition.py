from pathlib import Path

import pytest

from coeus.core.config import Settings
from coeus.main import create_app
from coeus.persistence.state_store import MemoryStateStore
from coeus.services.jioc_routing_context import LiveRoutingOperationalContext
from coeus.services.object_storage import LocalObjectStorage


def local_test_settings(tmp_path: Path, **overrides: object) -> Settings:
    values: dict[str, object] = {
        "audit_log_path": str(tmp_path / "audit.jsonl"),
        "environment": "test",
        "local_object_storage_path": str(tmp_path / "objects"),
        "persistence_provider": "memory",
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


def test_composition_uses_local_resources_and_preserves_state_aliases(tmp_path: Path) -> None:
    app = create_app(local_test_settings(tmp_path))

    assert isinstance(app.state.state_store, MemoryStateStore)
    assert isinstance(app.state.object_storage, LocalObjectStorage)
    assert app.state.settings.environment == "test"
    assert app.state.auth_service is not None
    assert app.state.registration_service is not None
    assert app.state.admin_analytics_service is not None
    assert app.state.store_services is not None
    assert app.state.ticket_services is not None
    assert app.state.quality_control_service is not None


def test_composition_shares_identity_audit_store_and_workflow_instances(tmp_path: Path) -> None:
    app = create_app(local_test_settings(tmp_path))
    auth = app.state.auth_service
    registration = app.state.registration_service
    access = app.state.access_services
    store = app.state.store_services
    analyst = app.state.analyst_workflow_service
    quality_control = app.state.quality_control_service

    assert registration._users is auth._users
    assert access.acgs._audit_log is auth.audit_log
    assert registration._audit_log is auth.audit_log
    assert analyst._audit_log is auth.audit_log
    assert quality_control._audit_log is auth.audit_log
    assert analyst._store is store
    assert quality_control._ingestion._store is store
    assert quality_control._ingestion._storage is app.state.object_storage
    routing_context = app.state.jioc_routing_agent_service._operational_context
    assert isinstance(routing_context, LiveRoutingOperationalContext)
    assert routing_context._teams is app.state.team_repository
    assert routing_context._availability is app.state.team_availability_service


def test_composition_rejects_inactive_future_object_storage(tmp_path: Path) -> None:
    settings = local_test_settings(tmp_path, object_storage_provider="gcs")

    with pytest.raises(ValueError, match="must remain local"):
        create_app(settings)
