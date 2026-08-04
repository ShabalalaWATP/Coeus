"""Deterministic operational work used by the local exercise fixture."""

from dataclasses import dataclass
from datetime import date, timedelta
from uuid import NAMESPACE_URL, UUID, uuid5

from coeus.domain.enums import TicketState
from coeus.domain.team_task_ownership import TeamTaskOwnershipState, WorkflowLeg
from coeus.domain.work_packages import CanonicalWorkPackageState
from coeus.repositories.synthetic_organisation_manifest import BASELINE


@dataclass(frozen=True)
class SyntheticTaskSpec:
    key: str
    reference: str
    title: str
    unit_key: str
    manager_username: str
    requester_username: str
    workflow_leg: WorkflowLeg
    ticket_state: TicketState
    ownership_state: TeamTaskOwnershipState
    assignee_username: str | None
    priority: str
    target_offset_days: int
    package_state: CanonicalWorkPackageState

    @property
    def ticket_id(self) -> UUID:
        return _stable_id("ticket", self.key)

    @property
    def ownership_id(self) -> UUID:
        return _stable_id("ownership", self.key)

    @property
    def history_reference(self) -> UUID:
        return _stable_id("ownership-history", self.key)

    @property
    def target_date(self) -> date:
        return (BASELINE + timedelta(days=self.target_offset_days)).date()

    def package_id(self, order: int) -> UUID:
        return _stable_id("work-package", f"{self.key}:{order}")

    def package_history_id(self, order: int) -> UUID:
        return _stable_id("work-package-history", f"{self.key}:{order}")

    def package_command_id(self, order: int) -> UUID:
        return _stable_id("work-package-command", f"{self.key}:{order}")


def synthetic_task_specs() -> tuple[SyntheticTaskSpec, ...]:
    from coeus.repositories.synthetic_task_manifest_cm import synthetic_cm_task_specs
    from coeus.repositories.synthetic_workload_distribution import distribute_synthetic_tasks

    rfa = WorkflowLeg.RFA
    tasks = (
        _task(
            "mar-1",
            "EXR-2001",
            "Baltic maritime activity baseline",
            "rfa_maritime",
            "rfa.team@example.test",
            "user@example.test",
            rfa,
            TicketState.ANALYST_ASSIGNMENT,
            None,
            "Routine",
            12,
        ),
        _task(
            "mar-2",
            "EXR-2002",
            "North Sea shipping pattern assessment",
            "rfa_maritime",
            "rfa.team@example.test",
            "customer.3@example.test",
            rfa,
            TicketState.ANALYST_IN_PROGRESS,
            True,
            "High",
            5,
        ),
        _task(
            "mar-3",
            "EXR-2003",
            "Port access risk assessment",
            "rfa_maritime",
            "rfa.team@example.test",
            "customer.4@example.test",
            rfa,
            TicketState.MANAGER_APPROVAL,
            True,
            "Routine",
            3,
        ),
        _task(
            "land-1",
            "EXR-2004",
            "Eastern training-area force posture",
            "rfa_land",
            "rfa.lead.2@example.test",
            "colleague@example.test",
            rfa,
            TicketState.ANALYST_IN_PROGRESS,
            True,
            "Urgent",
            1,
        ),
        _task(
            "land-2",
            "EXR-2005",
            "Synthetic ground movement assessment",
            "rfa_land",
            "rfa.lead.2@example.test",
            "customer.5@example.test",
            rfa,
            TicketState.ANALYST_IN_PROGRESS,
            True,
            "High",
            4,
            CanonicalWorkPackageState.BLOCKED,
        ),
        _task(
            "land-3",
            "EXR-2006",
            "Exercise logistics network review",
            "rfa_land",
            "rfa.lead.2@example.test",
            "customer.6@example.test",
            rfa,
            TicketState.REWORK_REQUIRED,
            True,
            "Routine",
            6,
        ),
        _task(
            "cyb-1",
            "EXR-2007",
            "Technical infrastructure exposure",
            "rfa_cyber",
            "rfa.lead.3@example.test",
            "user@example.test",
            rfa,
            TicketState.ANALYST_ASSIGNMENT,
            None,
            "Routine",
            14,
        ),
        _task(
            "cyb-2",
            "EXR-2008",
            "Synthetic network indicator assessment",
            "rfa_cyber",
            "rfa.lead.3@example.test",
            "customer.3@example.test",
            rfa,
            TicketState.ANALYST_IN_PROGRESS,
            True,
            "High",
            5,
        ),
        _task(
            "cyb-3",
            "EXR-2009",
            "Communications resilience estimate",
            "rfa_cyber",
            "rfa.lead.3@example.test",
            "customer.4@example.test",
            rfa,
            TicketState.QC_REVIEW,
            True,
            "Routine",
            2,
        ),
        _task(
            "reg-1",
            "EXR-2010",
            "Regional influence activity summary",
            "rfa_regional",
            "rfa.lead.4@example.test",
            "colleague@example.test",
            rfa,
            TicketState.ANALYST_ASSIGNMENT,
            None,
            "Routine",
            10,
        ),
        _task(
            "reg-2",
            "EXR-2011",
            "Open-source regional trend assessment",
            "rfa_regional",
            "rfa.lead.4@example.test",
            "customer.5@example.test",
            rfa,
            TicketState.ANALYST_IN_PROGRESS,
            True,
            "High",
            4,
        ),
        _task(
            "reg-3",
            "EXR-2012",
            "Partner reporting comparison",
            "rfa_regional",
            "rfa.lead.4@example.test",
            "customer.6@example.test",
            rfa,
            TicketState.MANAGER_APPROVAL,
            True,
            "Routine",
            3,
        ),
        *synthetic_cm_task_specs(),
        _closed(
            "closed-mar",
            "EXR-2022",
            "Completed maritime exercise brief",
            "rfa_maritime",
            "rfa.team@example.test",
            True,
            rfa,
        ),
    )
    return distribute_synthetic_tasks(tasks)


def _task(
    key: str,
    reference: str,
    title: str,
    unit: str,
    manager: str,
    requester: str,
    leg: WorkflowLeg,
    state: TicketState,
    assigned: bool | None,
    priority: str,
    due: int,
    package_state: CanonicalWorkPackageState | None = None,
) -> SyntheticTaskSpec:
    has_assignee = assigned is True
    resolved = package_state or _package_state(state, has_assignee)
    ownership = TeamTaskOwnershipState.ACTIVE if has_assignee else TeamTaskOwnershipState.PROPOSED
    return SyntheticTaskSpec(
        key,
        reference,
        title,
        unit,
        manager,
        requester,
        leg,
        state,
        ownership,
        "__capacity_allocate__" if has_assignee else None,
        priority,
        due,
        resolved,
    )


def _closed(
    key: str, reference: str, title: str, unit: str, manager: str, assigned: bool, leg: WorkflowLeg
) -> SyntheticTaskSpec:
    return SyntheticTaskSpec(
        key,
        reference,
        title,
        unit,
        manager,
        "user@example.test",
        leg,
        TicketState.CLOSED_DELIVERED,
        TeamTaskOwnershipState.COMPLETED,
        "__capacity_allocate__" if assigned else None,
        "Routine",
        -2,
        CanonicalWorkPackageState.COMPLETE,
    )


def _package_state(state: TicketState, assigned: bool) -> CanonicalWorkPackageState:
    if not assigned:
        return CanonicalWorkPackageState.PENDING
    if state in {TicketState.MANAGER_APPROVAL, TicketState.QC_REVIEW}:
        return CanonicalWorkPackageState.COMPLETE
    return CanonicalWorkPackageState.IN_PROGRESS


def _stable_id(kind: str, key: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"coeus:synthetic-{kind}:v1:{key}")
