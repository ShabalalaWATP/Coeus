"""Relational JIOC context composition follows organisation authority."""

from types import SimpleNamespace
from typing import cast

import pytest
from fastapi import FastAPI

from coeus.core.config import Settings
from coeus.domain.jioc_routing import JiocRoutingMode
from coeus.jioc_routing_composition import routing_operational_context
from coeus.persistence.jioc_routing_context_postgres import (
    PostgresShadowRoutingOperationalContext,
)
from coeus.services.jioc_routing_context import LiveRoutingOperationalContext


def _app() -> FastAPI:
    return cast(
        FastAPI,
        SimpleNamespace(
            state=SimpleNamespace(
                team_repository=object(),
                team_availability_service=object(),
                organisation_engine=object(),
            )
        ),
    )


def test_relational_context_requires_management_and_explicit_shadow_mode() -> None:
    active = Settings(
        environment="test",
        organisation_mode="management",
        jioc_agent_routing_enabled=JiocRoutingMode.ACTIVE,
    )
    assert isinstance(routing_operational_context(_app(), active), LiveRoutingOperationalContext)

    shadow = Settings(
        environment="test",
        organisation_mode="management",
        jioc_agent_routing_enabled=JiocRoutingMode.SHADOW,
    )
    assert isinstance(
        routing_operational_context(_app(), shadow),
        PostgresShadowRoutingOperationalContext,
    )

    disabled_organisation = Settings(
        environment="test",
        organisation_mode="disabled",
        jioc_agent_routing_enabled=JiocRoutingMode.SHADOW,
    )
    assert isinstance(
        routing_operational_context(_app(), disabled_organisation),
        LiveRoutingOperationalContext,
    )


def test_active_organisation_authority_always_uses_relational_capacity() -> None:
    settings = Settings(environment="test", organisation_mode="active")
    assert isinstance(
        routing_operational_context(_app(), settings),
        PostgresShadowRoutingOperationalContext,
    )


def test_active_organisation_authority_fails_closed_without_engine() -> None:
    app = _app()
    app.state.organisation_engine = None
    settings = Settings(environment="test", organisation_mode="active")
    with pytest.raises(RuntimeError, match="relational authority"):
        routing_operational_context(app, settings)
