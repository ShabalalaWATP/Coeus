"""Composition gate for the relational JIOC operational context."""

from fastapi import FastAPI

from coeus.core.config import Settings
from coeus.domain.jioc_routing import JiocRoutingMode, normalise_routing_mode
from coeus.persistence.jioc_routing_context_postgres import (
    PostgresShadowRoutingOperationalContext,
)
from coeus.services.jioc_routing_context import (
    LiveRoutingOperationalContext,
    RoutingOperationalContextPort,
)


def routing_operational_context(app: FastAPI, settings: Settings) -> RoutingOperationalContextPort:
    legacy: RoutingOperationalContextPort = LiveRoutingOperationalContext(
        app.state.team_repository,
        app.state.team_availability_service,
    )
    if settings.organisation_mode == "active":
        if app.state.organisation_engine is None:
            raise RuntimeError("Active organisation routing requires relational authority.")
        return PostgresShadowRoutingOperationalContext(app.state.organisation_engine)
    if (
        settings.organisation_mode != "management"
        or normalise_routing_mode(settings.jioc_agent_routing_enabled) is not JiocRoutingMode.SHADOW
        or app.state.organisation_engine is None
    ):
        return legacy
    return PostgresShadowRoutingOperationalContext(app.state.organisation_engine)
