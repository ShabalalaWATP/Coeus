"""Least-privilege management grants for the exercise hierarchy."""

from dataclasses import dataclass
from uuid import NAMESPACE_URL, UUID, uuid5

from coeus.domain.jioc_principals import JIOC_AGENT_PRINCIPAL, JIOC_CAPACITY_GRANT_ID
from coeus.domain.organisation import ManagementAction

AREA_ACTIONS = (
    ManagementAction.ORGANISATION_VIEW,
    ManagementAction.ORGANISATION_VIEW_AGGREGATE,
    ManagementAction.ROSTER_VIEW,
    ManagementAction.CALENDAR_VIEW_AVAILABILITY,
    ManagementAction.TASK_VIEW,
    ManagementAction.TASK_ASSIGN,
    ManagementAction.WORKSPACE_VIEW,
)
LEAF_ACTIONS = (
    ManagementAction.ORGANISATION_VIEW,
    ManagementAction.ROSTER_VIEW,
    ManagementAction.ROSTER_MANAGE,
    ManagementAction.CALENDAR_VIEW_AVAILABILITY,
    ManagementAction.CALENDAR_MANAGE,
    ManagementAction.TASK_VIEW,
    ManagementAction.TASK_ASSIGN,
    ManagementAction.WORKSPACE_VIEW,
)


@dataclass(frozen=True)
class SyntheticManagementGrantSpec:
    username: str
    unit_key: str
    action: ManagementAction
    include_descendants: bool

    @property
    def key(self) -> str:
        return f"{self.username}:{self.unit_key}:{self.action.value}"

    @property
    def grant_id(self) -> UUID:
        return uuid5(NAMESPACE_URL, f"coeus:synthetic-management-grant:v2:{self.key}")


@dataclass(frozen=True)
class SyntheticServiceGrantSpec:
    grant_id: UUID
    principal_id: UUID
    unit_key: str
    action: ManagementAction
    include_descendants: bool

    @property
    def key(self) -> str:
        return f"{self.principal_id}:{self.unit_key}:{self.action.value}"


def synthetic_service_grants() -> tuple[SyntheticServiceGrantSpec, ...]:
    return (
        SyntheticServiceGrantSpec(
            JIOC_CAPACITY_GRANT_ID,
            JIOC_AGENT_PRINCIPAL,
            "joint",
            ManagementAction.RECOMMENDATION_VIEW,
            True,
        ),
    )


def synthetic_management_grants() -> tuple[SyntheticManagementGrantSpec, ...]:
    rows: list[SyntheticManagementGrantSpec] = []
    for username, unit_key in (
        ("rfa.manager@example.test", "rfa"),
        ("collection.manager@example.test", "cm"),
    ):
        rows.extend(_grants(username, unit_key, AREA_ACTIONS, descendants=True))
    for username, unit_key in (
        ("rfa.team@example.test", "rfa_maritime"),
        ("rfa.lead.2@example.test", "rfa_land"),
        ("rfa.lead.3@example.test", "rfa_cyber"),
        ("rfa.lead.4@example.test", "rfa_regional"),
        ("collection.team@example.test", "cm_open"),
        ("cm.lead.2@example.test", "cm_geo"),
        ("cm.lead.3@example.test", "cm_requirements"),
    ):
        rows.extend(_grants(username, unit_key, LEAF_ACTIONS))
    rows.extend(
        _grants(
            "jioc.team@example.test",
            "joint",
            (
                ManagementAction.ORGANISATION_VIEW_AGGREGATE,
                ManagementAction.TASK_VIEW,
                ManagementAction.RECOMMENDATION_VIEW,
                ManagementAction.WORKSPACE_VIEW,
            ),
            descendants=True,
        )
    )
    rows.extend(
        _grants(
            "qc.manager@example.test",
            "qc",
            (
                ManagementAction.ORGANISATION_VIEW,
                ManagementAction.TASK_VIEW,
                ManagementAction.WORKSPACE_VIEW,
            ),
        )
    )
    rows.extend(
        _grants(
            "store.manager@example.test",
            "store",
            (ManagementAction.ORGANISATION_VIEW, ManagementAction.WORKSPACE_VIEW),
        )
    )
    rows.extend(
        _grants(
            "admin.2@example.test",
            "di",
            (
                ManagementAction.ORGANISATION_VIEW,
                ManagementAction.ORGANISATION_VIEW_AGGREGATE,
                ManagementAction.WORKSPACE_VIEW,
            ),
            descendants=True,
        )
    )
    return tuple(rows)


def _grants(
    username: str,
    unit_key: str,
    actions: tuple[ManagementAction, ...],
    *,
    descendants: bool = False,
) -> list[SyntheticManagementGrantSpec]:
    return [
        SyntheticManagementGrantSpec(username, unit_key, action, descendants) for action in actions
    ]
