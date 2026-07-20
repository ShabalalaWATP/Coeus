from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class JiocIntervention:
    intervention_id: UUID
    ticket_id: UUID
    action: str
    reason: str
    previous_state: str
    actor_user_id: UUID
    created_at: datetime
    resumed_at: datetime | None = None
    resumed_by_user_id: UUID | None = None
