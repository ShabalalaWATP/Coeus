"""Application boundary for repeatable ownership reconciliation."""

from coeus.application.ports.task_ownership_reconciliation import (
    TaskOwnershipReconciliationStore,
)
from coeus.domain.task_ownership_reconciliation import TaskOwnershipReconciliationResult


class TaskOwnershipReconciliationService:
    def __init__(self, store: TaskOwnershipReconciliationStore) -> None:
        self._store = store

    def reconcile(self) -> TaskOwnershipReconciliationResult:
        return self._store.reconcile()
