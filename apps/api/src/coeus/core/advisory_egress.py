"""Hosted security gates for remote advisory-agent data egress."""

from __future__ import annotations

from typing import TYPE_CHECKING

from coeus.domain.jioc_routing import JiocRoutingMode, normalise_routing_mode

HOSTED_ENVIRONMENTS = frozenset({"dev", "staging", "prod"})

if TYPE_CHECKING:
    from coeus.core.config import Settings


def advisory_egress_errors(settings: Settings) -> tuple[str, ...]:
    if settings.environment not in HOSTED_ENVIRONMENTS:
        return ()
    errors: list[str] = []
    enabled = settings.search_planner_remote_enabled or settings.routing_critic_remote_enabled
    if enabled and settings.llm_provider != "mock":
        if settings.llm_provider not in settings.advisory_approved_providers:
            errors.append(
                "COEUS_ADVISORY_APPROVED_PROVIDERS must include the selected remote provider."
            )
        if "synthetic" not in settings.advisory_approved_data_classifications:
            errors.append("COEUS_ADVISORY_APPROVED_DATA_CLASSIFICATIONS must include synthetic.")
    routing_enabled = (
        normalise_routing_mode(settings.jioc_agent_routing_enabled) is not JiocRoutingMode.DISABLED
    )
    if routing_enabled and (
        settings.persistence_provider != "postgres"
        or settings.ticket_persistence_mode != "relational"
    ):
        errors.append("Hosted JIOC routing requires PostgreSQL relational ticket persistence.")
    if (
        settings.routing_critic_remote_enabled
        and settings.outbox_lease_seconds <= settings.llm_api_timeout_seconds + 5
    ):
        errors.append(
            "COEUS_OUTBOX_LEASE_SECONDS must exceed the LLM timeout by more than 5 seconds."
        )
    return tuple(errors)
