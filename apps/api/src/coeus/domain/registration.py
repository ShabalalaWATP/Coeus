from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class RegistrationStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


@dataclass(frozen=True)
class RegistrationRequest:
    registration_id: UUID
    username: str
    display_name: str
    justification: str
    password_hash: str | None
    status: RegistrationStatus
    created_at: datetime
    decided_at: datetime | None
    decided_by_user_id: UUID | None
