"""Persistence contract for historical assignment ownership reconciliation."""

from typing import Protocol

from coeus.domain.task_ownership_reconciliation import TaskOwnershipReconciliationResult


class TaskOwnershipReconciliationStore(Protocol):
    def reconcile(self) -> TaskOwnershipReconciliationResult: ...
