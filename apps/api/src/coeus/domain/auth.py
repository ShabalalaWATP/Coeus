from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from coeus.core.permissions import Permission


class RoleName(StrEnum):
    ADMINISTRATOR = "Administrator"
    USER = "Customer"
    JIOC_TEAM_MEMBER = "JIOC Team Member"
    JIOC_MANAGER = "JIOC Manager"
    RFA_MANAGER = "RFA Manager"
    RFA_TEAM_MEMBER = "RFA Team Member"
    COLLECTION_MANAGER = "CM Manager"
    COLLECTION_TEAM_MEMBER = "CM Team Member"
    INTELLIGENCE_STORE_MANAGER = "Intelligence Store Manager"
    INTELLIGENCE_ANALYST = "Analyst"
    QUALITY_CONTROL_MANAGER = "Quality Control Manager"

    @classmethod
    def _missing_(cls, value: object) -> "RoleName | None":
        # Legacy role names persisted before the JIOC restructure still
        # decode; the codec reconstructs enums by value.
        return _LEGACY_ROLE_NAMES.get(value) if isinstance(value, str) else None


_LEGACY_ROLE_NAMES: dict[str, RoleName] = {
    "User": RoleName.USER,
    "Request for Assessment Manager": RoleName.RFA_MANAGER,
    "Request for Assessment Team Member": RoleName.RFA_TEAM_MEMBER,
    "Collection Manager": RoleName.COLLECTION_MANAGER,
    "Collection Team Member": RoleName.COLLECTION_TEAM_MEMBER,
    "Intelligence Analyst": RoleName.INTELLIGENCE_ANALYST,
}


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
    credential_version: int = 0


@dataclass(frozen=True)
class SessionRecord:
    session_id: str
    user_id: UUID
    csrf_token: str
    expires_at: datetime
    created_at: datetime
    credential_version: int = 0


@dataclass(frozen=True)
class AuthenticatedSession:
    session: SessionRecord
    user: UserAccount
