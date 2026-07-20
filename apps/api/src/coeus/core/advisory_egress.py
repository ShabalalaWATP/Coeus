"""Hosted security gates for remote advisory-agent data egress."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from coeus.core.deployment import HOSTED_ENVIRONMENTS
from coeus.domain.jioc_routing import JiocRoutingMode, normalise_routing_mode


class AdvisoryEgressSettings(Protocol):
    @property
    def environment(self) -> str: ...

    @property
    def search_planner_remote_enabled(self) -> bool: ...

    @property
    def routing_critic_remote_enabled(self) -> bool: ...

    @property
    def llm_provider(self) -> str: ...

    @property
    def advisory_approved_providers(self) -> Sequence[str]: ...

    @property
    def advisory_approved_data_classifications(self) -> Sequence[str]: ...

    @property
    def jioc_agent_routing_enabled(self) -> JiocRoutingMode | bool: ...

    @property
    def persistence_provider(self) -> str: ...

    @property
    def ticket_persistence_mode(self) -> str: ...

    @property
    def outbox_lease_seconds(self) -> int: ...

    @property
    def llm_api_timeout_seconds(self) -> int: ...


def advisory_egress_errors(settings: AdvisoryEgressSettings) -> tuple[str, ...]:
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
