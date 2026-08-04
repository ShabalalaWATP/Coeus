"""Results from safe historical assignment ownership reconciliation."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class TaskOwnershipReconciliationResult:
    checkpoint_id: UUID
    as_of: datetime
    scanned_tickets: int
    created_ownerships: int
    existing_ownerships: int
    findings: int
    already_applied: bool = False


class TaskOwnershipReconciliationLimit(RuntimeError):
    """The bounded automatic reconciliation needs an operator-managed batch."""
