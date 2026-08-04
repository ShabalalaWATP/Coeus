"""Machine-readable live integrity evidence for the synthetic workforce."""

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.engine import Connection

from coeus.repositories.access import AccessRepository
from coeus.repositories.synthetic_access_manifest import synthetic_analyst_acg_codes
from coeus.repositories.synthetic_capacity_manifest import synthetic_capacity_reservations
from coeus.repositories.synthetic_organisation_manifest import synthetic_posting_specs
from coeus.repositories.synthetic_task_manifest import synthetic_task_specs


@dataclass(frozen=True)
class LiveSyntheticFixtureIntegrityReport:
    duplicate_team_names: int
    overlapping_memberships: int
    missing_task_ownership: int
    maximum_active_packages_per_analyst: int
    workload_concentration_count: int
    missing_reservations: int
    invalid_reservations: int
    acg_authorisation_gaps: int
    clearance_gaps: int
    transfer_evidence_gaps: int
    suspended_account_gaps: int
    errors: tuple[str, ...]

    @property
    def valid(self) -> bool:
        return not self.errors


def inspect_live_synthetic_fixture(
    connection: Connection,
    access: AccessRepository,
) -> LiveSyntheticFixtureIntegrityReport:
    duplicate_teams = _scalar(
        connection,
        "SELECT count(*) FROM (SELECT lower(name) FROM organisation_units "
        "WHERE is_active GROUP BY lower(name) HAVING count(*)>1) duplicate",
    )
    overlaps = _scalar(
        connection,
        "SELECT count(*) FROM team_memberships left_row JOIN team_memberships right_row "
        "ON left_row.user_id=right_row.user_id AND left_row.membership_id<right_row.membership_id "
        "AND tstzrange(left_row.valid_from,coalesce(left_row.valid_until,'infinity')) && "
        "tstzrange(right_row.valid_from,coalesce(right_row.valid_until,'infinity')) "
        "WHERE left_row.state='active' AND right_row.state='active'",
    )
    tasks = synthetic_task_specs()
    ownership_rows = set(
        connection.execute(
            text("SELECT ownership_id FROM team_task_ownership WHERE ownership_id=ANY(:ids)"),
            {"ids": [item.ownership_id for item in tasks]},
        ).scalars()
    )
    load_rows = tuple(
        connection.execute(
            text(
                "SELECT accountable_user_id,count(*) FROM canonical_work_packages "
                "WHERE accountable_user_id IS NOT NULL "
                "AND state IN ('ready','in_progress','blocked') "
                "GROUP BY accountable_user_id"
            )
        ).all()
    )
    maximum_load = max((int(row[1]) for row in load_rows), default=0)
    concentrated = sum(int(row[1]) >= 4 for row in load_rows)
    reservation_specs = synthetic_capacity_reservations()
    reservation_rows = {
        row[0]: row
        for row in connection.execute(
            text(
                "SELECT reservation_id,reserved_minutes,state FROM capacity_reservations "
                "WHERE reservation_id=ANY(:ids)"
            ),
            {"ids": [item.reservation_id for item in reservation_specs]},
        ).all()
    }
    invalid_reservations = sum(
        row is not None and (int(row[1]) != spec.minutes or row[2] != "active")
        for spec in reservation_specs
        if (row := reservation_rows.get(spec.reservation_id)) is not None
    )
    acg_codes = {item.acg_id: item.code for item in access.list_acgs() if item.is_active}
    expected_acgs = synthetic_analyst_acg_codes()
    acg_gaps = 0
    clearance_gaps = 0
    for task in tasks:
        if task.assignee_username is None:
            continue
        account = access.get_user_by_username(task.assignee_username)
        if account is None or account.clearance_level < 2:
            clearance_gaps += 1
            continue
        actual_codes = {
            acg_codes[item]
            for item in access.active_acg_ids_for_user(account.user_id)
            if item in acg_codes
        }
        if not actual_codes.intersection(expected_acgs[task.assignee_username]):
            acg_gaps += 1
    transfer_specs = [
        item for item in synthetic_posting_specs() if item.username == "analyst.13@example.test"
    ]
    transfer_rows = _scalar(
        connection,
        "SELECT count(*) FROM team_memberships WHERE membership_id=ANY(:ids)",
        {"ids": [item.membership_id for item in transfer_specs]},
    )
    unavailable = access.get_user_by_username("analyst.24@example.test")
    suspended_gap = int(unavailable is None or unavailable.is_active)
    values = {
        "duplicate_team_names": duplicate_teams,
        "overlapping_memberships": overlaps,
        "missing_task_ownership": len(tasks) - len(ownership_rows),
        "missing_reservations": len(reservation_specs) - len(reservation_rows),
        "invalid_reservations": invalid_reservations,
        "acg_authorisation_gaps": acg_gaps,
        "clearance_gaps": clearance_gaps,
        "transfer_evidence_gaps": len(transfer_specs) - transfer_rows,
        "suspended_account_gaps": suspended_gap,
    }
    errors = tuple(key for key, value in values.items() if value)
    return LiveSyntheticFixtureIntegrityReport(
        duplicate_teams,
        overlaps,
        len(tasks) - len(ownership_rows),
        maximum_load,
        concentrated,
        len(reservation_specs) - len(reservation_rows),
        invalid_reservations,
        acg_gaps,
        clearance_gaps,
        len(transfer_specs) - transfer_rows,
        suspended_gap,
        errors,
    )


def _scalar(connection: Connection, query: str, params: dict[str, object] | None = None) -> int:
    return int(connection.execute(text(query), params or {}).scalar_one())
