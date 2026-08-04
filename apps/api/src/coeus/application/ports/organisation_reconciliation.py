"""Atomic persistence boundary for organisation snapshot reconciliation."""

from typing import Protocol

from coeus.domain.organisation_reconciliation import OrganisationReconciliationPlan


class OrganisationReconciliationCommitter(Protocol):
    def apply_reconciliation(self, plan: OrganisationReconciliationPlan) -> None: ...
