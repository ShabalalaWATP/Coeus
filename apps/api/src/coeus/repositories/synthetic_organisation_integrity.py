"""Machine-readable integrity evidence for the relational exercise manifest."""

from collections import Counter
from dataclasses import dataclass

from coeus.domain.organisation import DeliveryRoute, MembershipState
from coeus.repositories.synthetic_access_manifest import synthetic_analyst_acg_codes
from coeus.repositories.synthetic_calendar_manifest import synthetic_calendar_events
from coeus.repositories.synthetic_capability_manifest import (
    TEAM_CAPABILITIES,
    synthetic_analyst_competencies,
    synthetic_team_capabilities,
)
from coeus.repositories.synthetic_capacity_manifest import (
    synthetic_capacity_reservations,
    synthetic_workload_scenarios,
)
from coeus.repositories.synthetic_grant_manifest import synthetic_management_grants
from coeus.repositories.synthetic_organisation_manifest import (
    SyntheticPostingSpec,
    synthetic_posting_specs,
    synthetic_unit_specs,
    synthetic_working_patterns,
)
from coeus.repositories.synthetic_task_manifest import synthetic_task_specs
from coeus.repositories.synthetic_workforce import ANALYST_CLEARANCE_LEVELS


@dataclass(frozen=True)
class SyntheticOrganisationIntegrityReport:
    unit_count: int
    posting_count: int
    analyst_count: int
    active_eligible_rfa_count: int
    active_eligible_cm_count: int
    working_pattern_count: int
    team_capability_count: int
    analyst_competency_count: int
    calendar_event_count: int
    scoped_management_grant_count: int
    task_count: int
    active_task_count: int
    closed_task_count: int
    work_package_count: int
    capacity_reservation_count: int
    transfer_evidence_count: int
    workload_scenario_count: int
    analyst_acg_variation_count: int
    analyst_clearance_variation_count: int
    duplicate_stable_id_count: int
    delivery_leaf_shortfalls: tuple[str, ...]
    errors: tuple[str, ...]

    @property
    def valid(self) -> bool:
        return not self.errors


def inspect_synthetic_organisation_manifest() -> SyntheticOrganisationIntegrityReport:
    units = synthetic_unit_specs()
    postings = synthetic_posting_specs()
    patterns = synthetic_working_patterns()
    team_capabilities = synthetic_team_capabilities()
    competencies = synthetic_analyst_competencies()
    calendar_events = synthetic_calendar_events()
    management_grants = synthetic_management_grants()
    tasks = synthetic_task_specs()
    reservations = synthetic_capacity_reservations()
    workload_scenarios = synthetic_workload_scenarios()
    analyst_acgs = synthetic_analyst_acg_codes()
    unit_by_key = {item.key: item for item in units}
    analyst_postings = tuple(
        item
        for item in postings
        if item.username == "analyst@example.test" or item.username.startswith("analyst.")
    )
    analyst_by_username: dict[str, SyntheticPostingSpec] = {}
    for posting in analyst_postings:
        analyst_by_username.setdefault(posting.username, posting)
    analysts = tuple(analyst_by_username.values())
    eligible = tuple(
        item
        for item in analysts
        if item.state is MembershipState.ACTIVE and item.assignment_eligible
    )
    rfa = sum(unit_by_key[item.unit_key].route is DeliveryRoute.RFA for item in eligible)
    cm = sum(unit_by_key[item.unit_key].route is DeliveryRoute.CM for item in eligible)
    leaf_counts = Counter(item.unit_key for item in eligible)
    shortfalls = tuple(
        sorted(item.key for item in units if item.route is not None and leaf_counts[item.key] < 3)
    )
    stable_ids = (
        [item.unit_id for item in units]
        + [item.membership_id for item in postings]
        + [item.pattern_id for item in patterns]
        + [item.coverage_id for item in team_capabilities]
        + [item.competency_id for item in competencies]
        + [item.event_id for item in calendar_events]
        + [item.history_id for item in calendar_events]
        + [item.command_id for item in calendar_events]
        + [item.grant_id for item in management_grants]
        + [item.ticket_id for item in tasks]
        + [item.ownership_id for item in tasks]
        + [item.history_reference for item in tasks]
        + [item.package_id(order) for item in tasks for order in (1, 2)]
        + [item.package_history_id(order) for item in tasks for order in (1, 2)]
        + [item.package_command_id(order) for item in tasks for order in (1, 2)]
    )
    competency_counts = Counter(item.username for item in competencies)
    home_by_user = {item.username: item.unit_key for item in analysts}
    errors: list[str] = []
    _expect(errors, len(units) == 25, "unit_count")
    _expect(errors, len(postings) == 54, "posting_count")
    _expect(errors, len({item.username for item in postings}) == 53, "person_count")
    open_homes = Counter(
        item.username for item in postings if item.state is not MembershipState.ENDED
    )
    # Historical postings are closed, so anything still open must be the one home.
    _expect(errors, all(count == 1 for count in open_homes.values()), "single_home_postings")
    _expect(errors, len(analysts) == 24, "analyst_count")
    _expect(errors, rfa == 12, "active_eligible_rfa_count")
    _expect(errors, cm == 9, "active_eligible_cm_count")
    _expect(errors, len(patterns) == 24, "working_pattern_count")
    _expect(errors, len(team_capabilities) == 61, "team_capability_count")
    _expect(errors, len(competencies) == 48, "analyst_competency_count")
    _expect(errors, len(calendar_events) == 8, "calendar_event_count")
    _expect(errors, len(management_grants) == 82, "scoped_management_grant_count")
    closed_tasks = tuple(item for item in tasks if item.ticket_state.value.startswith("CLOSED_"))
    active_tasks = tuple(item for item in tasks if item not in closed_tasks)
    _expect(errors, len(tasks) == 24, "task_count")
    _expect(errors, len(active_tasks) == 21, "active_task_count")
    _expect(errors, len(closed_tasks) == 3, "closed_task_count")
    _expect(errors, len(tasks) * 2 == 48, "work_package_count")
    transfer = tuple(item for item in postings if item.username == "analyst.13@example.test")
    _expect(errors, len(transfer) == 2, "transfer_evidence_count")
    _expect(
        errors,
        transfer[0].valid_from >= (transfer[1].valid_until or transfer[0].valid_from),
        "transfer_membership_overlap",
    )
    _expect(errors, len(reservations) == 2, "capacity_reservation_count")
    _expect(
        errors,
        {item.state for item in workload_scenarios}
        == {"idle", "loaded", "overloaded", "unavailable"},
        "workload_scenario_coverage",
    )
    workload_by_state = {item.state: item for item in workload_scenarios}
    _expect(
        errors,
        workload_by_state["loaded"].active_work_minutes
        + workload_by_state["loaded"].reserved_minutes
        < workload_by_state["loaded"].daily_capacity_minutes,
        "loaded_scenario_bounds",
    )
    _expect(
        errors,
        workload_by_state["overloaded"].active_work_minutes
        + workload_by_state["overloaded"].reserved_minutes
        > workload_by_state["overloaded"].daily_capacity_minutes,
        "overloaded_scenario_bounds",
    )
    _expect(errors, len(set(ANALYST_CLEARANCE_LEVELS.values())) >= 2, "clearance_variation")
    _expect(errors, len(set(analyst_acgs.values())) >= 7, "acg_variation")
    _expect(
        errors,
        all(
            item.assignee_username is None
            or home_by_user.get(item.assignee_username) == item.unit_key
            for item in tasks
        ),
        "task_assignee_home_team_alignment",
    )
    _expect(errors, not shortfalls, "delivery_leaf_shortfalls")
    _expect(errors, len(stable_ids) == len(set(stable_ids)), "duplicate_stable_ids")
    _expect(
        errors,
        all(competency_counts[item.username] == 2 for item in analysts),
        "analyst_competency_coverage",
    )
    _expect(
        errors,
        all(
            item.capability_id in TEAM_CAPABILITIES[home_by_user[item.username]]
            for item in competencies
        ),
        "competency_home_team_alignment",
    )
    return SyntheticOrganisationIntegrityReport(
        len(units),
        len(postings),
        len(analysts),
        rfa,
        cm,
        len(patterns),
        len(team_capabilities),
        len(competencies),
        len(calendar_events),
        len(management_grants),
        len(tasks),
        len(active_tasks),
        len(closed_tasks),
        len(tasks) * 2,
        len(reservations),
        len(transfer),
        len(workload_scenarios),
        len(set(analyst_acgs.values())),
        len(set(ANALYST_CLEARANCE_LEVELS.values())),
        len(stable_ids) - len(set(stable_ids)),
        shortfalls,
        tuple(errors),
    )


def _expect(errors: list[str], condition: bool, code: str) -> None:
    if not condition:
        errors.append(code)
