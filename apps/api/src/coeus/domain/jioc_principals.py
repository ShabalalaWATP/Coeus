"""Stable internal identities used by bounded JIOC automation.

Service status is an explicit registry decision. An absent human account must
never be interpreted as evidence that a principal is an internal service.
"""

from enum import StrEnum
from uuid import NAMESPACE_URL, UUID, uuid5

JIOC_AGENT_PRINCIPAL = UUID("00000000-0000-0000-0000-000000000002")
JIOC_CAPACITY_GRANT_ID = uuid5(
    NAMESPACE_URL,
    "coeus:jioc-agent:relational-capacity-shadow:recommendation-view:v1",
)


class PrincipalKind(StrEnum):
    HUMAN = "human"
    SERVICE = "service"


REGISTERED_SERVICE_PRINCIPALS = frozenset({JIOC_AGENT_PRINCIPAL})


def principal_kind(principal_id: UUID) -> PrincipalKind:
    """Classify only registered internal services; every other ID is human."""
    if principal_id in REGISTERED_SERVICE_PRINCIPALS:
        return PrincipalKind.SERVICE
    return PrincipalKind.HUMAN
