from dataclasses import dataclass

from coeus.core.permissions import Permission


@dataclass(frozen=True)
class AccessDecision:
    allowed: bool
    reason: str


def require_permission(user_permissions: set[Permission], permission: Permission) -> AccessDecision:
    if permission in user_permissions:
        return AccessDecision(allowed=True, reason="permission_granted")
    return AccessDecision(allowed=False, reason="permission_missing")
