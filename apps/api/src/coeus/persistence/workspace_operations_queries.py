"""Bounded SQL projections for integrated workspace operations."""

from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Connection, RowMapping

from coeus.domain.organisation import ManagementAction
from coeus.domain.workspace_operations import (
    CapabilityCoverage,
    PlanningCadence,
    WorkspaceAnalytics,
    WorkspaceOperationsDenied,
    WorkspaceOverview,
    WorkspacePerson,
    WorkspacePolicy,
    WorkspaceScope,
    WorkspaceSearchResult,
)
from coeus.persistence.organisation_authority_validation import transaction_time
from coeus.persistence.workspace_operations_authority import (
    has_effective_membership,
    resolve_workspace_authority,
)
from coeus.persistence.workspace_operations_metrics import (
    analytics_metrics as _analytics_metrics,
)
from coeus.persistence.workspace_operations_metrics import (
    metric_values as _metric_values,
)
from coeus.persistence.workspace_operations_metrics import (
    overview_metrics as _overview_metrics,
)


def overview(
    connection: Connection, actor: UUID, unit_id: UUID, scope: WorkspaceScope
) -> WorkspaceOverview:
    at = transaction_time(connection)
    authority = resolve_workspace_authority(
        connection, actor, unit_id, ManagementAction.WORKSPACE_VIEW, scope, at
    )
    values = _metric_values(connection, authority.unit_ids, at)
    suppressed = scope is WorkspaceScope.DESCENDANTS and values["headcount"] < 5
    metrics = _overview_metrics(values, scope, suppressed)
    return WorkspaceOverview(
        unit_id,
        scope,
        at,
        at + timedelta(minutes=15),
        metrics,
        len(authority.unit_ids) - 1,
        suppressed,
    )


def people(
    connection: Connection, actor: UUID, unit_id: UUID, scope: WorkspaceScope
) -> tuple[WorkspacePerson, ...]:
    at = transaction_time(connection)
    units = _roster_units(connection, actor, unit_id, scope, at)
    rows = connection.execute(text(_PEOPLE), {"units": list(units), "at": at}).mappings()
    return tuple(
        WorkspacePerson(
            UUID(str(row["user_id"])),
            str(row["role"]),
            bool(row["assignment_eligible"]),
            None if row["time_zone"] is None else str(row["time_zone"]),
            None if row["weekly_minutes"] is None else int(row["weekly_minutes"]),
        )
        for row in rows
    )


def _roster_units(
    connection: Connection, actor: UUID, unit_id: UUID, scope: WorkspaceScope, at: datetime
) -> tuple[UUID, ...]:
    for action in (ManagementAction.ROSTER_VIEW, ManagementAction.CAPABILITY_MANAGE):
        try:
            return resolve_workspace_authority(
                connection, actor, unit_id, action, scope, at
            ).unit_ids
        except WorkspaceOperationsDenied:
            continue
    # Being posted to a team is enough to see who else is in it. That is not
    # management authority, so it stops at the actor's own unit and never
    # reaches child teams, which stay grant-only.
    if scope is WorkspaceScope.DIRECT and has_effective_membership(connection, actor, unit_id, at):
        return (unit_id,)
    raise WorkspaceOperationsDenied


def capabilities(
    connection: Connection, actor: UUID, unit_id: UUID, scope: WorkspaceScope
) -> tuple[CapabilityCoverage, ...]:
    at = transaction_time(connection)
    authority = resolve_workspace_authority(
        connection, actor, unit_id, ManagementAction.ROSTER_VIEW, scope, at
    )
    cohort = _metric_values(connection, authority.unit_ids, at)["headcount"]
    suppress = scope is WorkspaceScope.DESCENDANTS and cohort < 5
    rows = connection.execute(
        text(_CAPABILITIES), {"units": list(authority.unit_ids), "at": at}
    ).mappings()
    return tuple(
        CapabilityCoverage(
            str(row["capability_id"]),
            int(row["proficiency"]),
            None if suppress else int(row["verified_people"]),
            "<5" if suppress else str(int(row["verified_people"])),
            None if suppress else int(row["verified_people"]) == 0,
            suppress,
        )
        for row in rows
    )


def policy(connection: Connection, actor: UUID, unit_id: UUID) -> WorkspacePolicy:
    at = transaction_time(connection)
    resolve_workspace_authority(
        connection, actor, unit_id, ManagementAction.WORKSPACE_VIEW, WorkspaceScope.DIRECT, at
    )
    row = connection.execute(text(_POLICY), {"unit": unit_id}).mappings().first()
    if row is None:
        from coeus.domain.workspace_operations import WorkspaceOperationsDenied

        raise WorkspaceOperationsDenied
    return _policy_row(row)


def search(
    connection: Connection,
    actor: UUID,
    unit_id: UUID,
    scope: WorkspaceScope,
    query: str,
    limit: int,
) -> tuple[WorkspaceSearchResult, ...]:
    at = transaction_time(connection)
    workspace = resolve_workspace_authority(
        connection, actor, unit_id, ManagementAction.WORKSPACE_VIEW, scope, at
    )
    rows: list[WorkspaceSearchResult] = []
    pattern = f"%{query}%"
    for row in connection.execute(
        text(_TEAM_SEARCH), {"units": list(workspace.unit_ids), "pattern": pattern, "limit": limit}
    ).mappings():
        rows.append(_search_row(row))
    try:
        roster = resolve_workspace_authority(
            connection, actor, unit_id, ManagementAction.ROSTER_VIEW, scope, at
        )
    except PermissionError:
        pass
    else:
        for row in connection.execute(
            text(_PEOPLE_SEARCH),
            {"units": list(roster.unit_ids), "limit": min(limit * 5, 101)},
        ).mappings():
            rows.append(_search_row(row))
    try:
        tasks = resolve_workspace_authority(
            connection, actor, unit_id, ManagementAction.TASK_VIEW, scope, at
        )
    except PermissionError:
        return tuple(rows[: min(limit * 3, 100)])
    for row in connection.execute(
        text(_WORK_SEARCH),
        {"units": list(tasks.unit_ids), "pattern": pattern, "limit": limit + 1},
    ).mappings():
        rows.append(_search_row(row))
    return tuple(rows[: min(limit * 3, 100)])


def analytics(
    connection: Connection, actor: UUID, unit_id: UUID, scope: WorkspaceScope
) -> WorkspaceAnalytics:
    at = transaction_time(connection)
    authority = resolve_workspace_authority(
        connection, actor, unit_id, ManagementAction.WORKSPACE_VIEW, scope, at
    )
    values = _metric_values(connection, authority.unit_ids, at)
    suppress = scope is WorkspaceScope.DESCENDANTS and values["headcount"] < 5
    metrics = _analytics_metrics(values, scope, suppress)
    return WorkspaceAnalytics(
        unit_id,
        scope,
        at,
        metrics,
        "Small descendant cohorts are suppressed. Metrics support team planning, "
        "not individual scoring.",
    )


def _policy_row(row: RowMapping) -> WorkspacePolicy:
    return WorkspacePolicy(
        UUID(str(row["unit_id"])),
        int(row["wip_limit"]),
        int(row["service_target_hours"]),
        PlanningCadence(str(row["planning_cadence"])),
        int(row["planning_weekday"]),
        row["planning_local_time"],
        int(row["planning_duration_minutes"]),
        int(row["version"]),
        int(row["policy_version"]),
        row["updated_at"],
    )


def _search_row(row: RowMapping) -> WorkspaceSearchResult:
    return WorkspaceSearchResult(
        str(row["result_type"]),
        UUID(str(row["object_id"])),
        UUID(str(row["unit_id"])),
        str(row["label"]),
        str(row["context"]),
    )


_PEOPLE = """
SELECT m.user_id,m.role,m.assignment_eligible,p.time_zone,
 (p.monday_minutes+p.tuesday_minutes+p.wednesday_minutes+p.thursday_minutes+
  p.friday_minutes+p.saturday_minutes+p.sunday_minutes) weekly_minutes
FROM team_memberships m JOIN identity_account_projection a ON a.user_id=m.user_id AND a.is_active
LEFT JOIN working_patterns p ON p.user_id=m.user_id AND p.valid_from<=:at
 AND (p.valid_until IS NULL OR :at<p.valid_until)
WHERE m.unit_id=ANY(CAST(:units AS uuid[])) AND m.state='active' AND m.valid_from<=:at
 AND (m.valid_until IS NULL OR :at<m.valid_until) ORDER BY m.user_id LIMIT 1001
"""

_CAPABILITIES = """
SELECT c.capability_id,max(c.proficiency) proficiency,count(DISTINCT a.user_id) verified_people
FROM team_delivery_profiles p JOIN team_capability_coverage c ON c.profile_id=p.profile_id
LEFT JOIN team_memberships m ON m.unit_id=p.unit_id AND m.state='active' AND m.valid_from<=:at
 AND (m.valid_until IS NULL OR :at<m.valid_until)
LEFT JOIN assignment_competencies a ON a.user_id=m.user_id AND a.capability_id=c.capability_id
 AND a.proficiency>=c.proficiency AND (a.expires_at IS NULL OR :at<a.expires_at)
WHERE p.unit_id=ANY(CAST(:units AS uuid[])) AND p.is_active AND c.valid_from<=:at
 AND (c.valid_until IS NULL OR :at<c.valid_until)
GROUP BY c.capability_id ORDER BY c.capability_id LIMIT 100
"""

_POLICY = """
SELECT p.unit_id,p.wip_limit,p.policy_version,
 COALESCE(w.service_target_hours,72) service_target_hours,
 COALESCE(w.planning_cadence,'weekly') planning_cadence,
 COALESCE(w.planning_weekday,0) planning_weekday,
 COALESCE(w.planning_local_time,'09:00'::time) planning_local_time,
 COALESCE(w.planning_duration_minutes,60) planning_duration_minutes,
 COALESCE(w.version,0) version,COALESCE(w.updated_at,p.updated_at) updated_at
FROM team_delivery_profiles p LEFT JOIN team_workspace_policies w ON w.unit_id=p.unit_id
WHERE p.unit_id=:unit AND p.is_active
"""

_TEAM_SEARCH = """
SELECT 'team' result_type,unit_id object_id,unit_id,name label,short_name context
FROM organisation_units WHERE unit_id=ANY(CAST(:units AS uuid[]))
AND (name ILIKE :pattern OR short_name ILIKE :pattern) ORDER BY name,unit_id LIMIT :limit
"""

_WORK_SEARCH = """
SELECT 'work_package' result_type,p.package_id object_id,p.owning_unit_id unit_id,
 p.title label,concat('Package · ',p.state) context FROM canonical_work_packages p
WHERE p.owning_unit_id=ANY(CAST(:units AS uuid[])) AND p.title ILIKE :pattern
UNION ALL
SELECT concat('store_',l.target_type),l.target_id,l.unit_id,l.label,
 concat('Linked ',l.target_type) FROM workspace_store_links l
WHERE l.unit_id=ANY(CAST(:units AS uuid[])) AND l.label ILIKE :pattern
ORDER BY label,object_id LIMIT :limit
"""

_PEOPLE_SEARCH = """
SELECT 'person' result_type,m.user_id object_id,m.unit_id,
 CAST(m.user_id AS text) label,concat('Person · ',m.role) context
FROM team_memberships m JOIN identity_account_projection a ON a.user_id=m.user_id AND a.is_active
WHERE m.unit_id=ANY(CAST(:units AS uuid[])) AND m.state='active'
ORDER BY m.user_id LIMIT :limit
"""
