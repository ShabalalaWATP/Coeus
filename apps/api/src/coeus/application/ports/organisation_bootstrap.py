"""Transactional port for the one-shot organisation bootstrap ceremony."""

from typing import Protocol

from coeus.domain.organisation_bootstrap import (
    OrganisationBootstrapPlan,
    OrganisationBootstrapResult,
)


class OrganisationBootstrapStore(Protocol):
    def bootstrap(self, plan: OrganisationBootstrapPlan) -> OrganisationBootstrapResult: ...
