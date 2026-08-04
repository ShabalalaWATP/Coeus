"""Compose trusted hosted outbox handlers without widening HTTP trust."""

from fastapi import FastAPI
from sqlalchemy.engine import Engine

from coeus.api.identity_composition import IdentityComponents
from coeus.api.ticket_discovery_composition import build_ticket_discovery_handler
from coeus.domain.work_update_events import WORK_UPDATE_REQUESTED
from coeus.persistence.work_update_projection_postgres import PostgresWorkUpdateProjection
from coeus.services.outbox_dispatcher import OutboxHandler
from coeus.services.release_notification_handler import ProductReleaseNotificationHandler
from coeus.services.routing_critic_agent import RoutingCriticAgent
from coeus.services.routing_critic_intent import ROUTING_CRITIQUE_REQUESTED
from coeus.services.routing_critic_outbox_handler import RoutingCriticOutboxHandler
from coeus.services.tickets import TicketServices
from coeus.services.work_update_outbox_handler import WorkUpdateOutboxHandler


def build_runtime_outbox_handlers(
    app: FastAPI,
    identity: IdentityComponents,
    tickets: TicketServices,
    critic: RoutingCriticAgent,
) -> dict[str, OutboxHandler]:
    handlers: dict[str, OutboxHandler] = {
        "ticket_shadow_changed": build_ticket_discovery_handler(app, identity.access),
        "product_release_notification": ProductReleaseNotificationHandler(
            identity.users, app.state.notification_service
        ),
        ROUTING_CRITIQUE_REQUESTED: RoutingCriticOutboxHandler(tickets, critic),
    }
    engine = getattr(app.state, "organisation_engine", None)
    if isinstance(engine, Engine):
        handlers[WORK_UPDATE_REQUESTED] = WorkUpdateOutboxHandler(
            PostgresWorkUpdateProjection(engine)
        )
    return handlers
