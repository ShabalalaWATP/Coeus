from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from coeus.core.permissions import Permission


class RoleName(StrEnum):
    ADMINISTRATOR = "Administrator"
    USER = "User"
    RFA_MANAGER = "Request for Assessment Manager"
    RFA_TEAM_MEMBER = "Request for Assessment Team Member"
    COLLECTION_MANAGER = "Collection Manager"
    COLLECTION_TEAM_MEMBER = "Collection Team Member"
    INTELLIGENCE_STORE_MANAGER = "Intelligence Store Manager"
    INTELLIGENCE_ANALYST = "Intelligence Analyst"
    QUALITY_CONTROL_MANAGER = "Quality Control Manager"


@dataclass(frozen=True)
class RoleDefinition:
    name: RoleName
    default_route: str
    permissions: frozenset[Permission]


@dataclass
class UserAccount:
    user_id: UUID
    username: str
    display_name: str
    roles: frozenset[RoleName]
    permissions: frozenset[Permission]
    password_hash: str
    is_active: bool
    clearance_level: int
    password_reset_required: bool = False


@dataclass(frozen=True)
class SessionRecord:
    session_id: str
    user_id: UUID
    csrf_token: str
    expires_at: datetime
    created_at: datetime


@dataclass(frozen=True)
class AuthenticatedSession:
    session: SessionRecord
    user: UserAccount
