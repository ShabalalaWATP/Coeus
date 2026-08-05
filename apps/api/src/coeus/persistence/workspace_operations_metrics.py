"""Forecast-backed, privacy-suppressible workspace operational metrics."""

from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Connection

from coeus.domain.workspace_operations import WorkspaceMetric, WorkspaceScope
from coeus.persistence.team_capacity_forecast_postgres import forecast_team_in_transaction


def metric_values(
    connection: Connection, unit_ids: tuple[UUID, ...], at: datetime
) -> dict[str, int]:
    row = connection.execute(text(_METRICS), {"units": list(unit_ids), "at": at}).mappings().one()
    values = {key: int(row[key] or 0) for key in row}
    values["available_minutes"] = sum(
        forecast_team_in_transaction(
            connection, unit_id, at, at + timedelta(days=7), at
        ).assignable_minutes
        for unit_id in unit_ids
    )
    return values


def overview_metrics(
    values: dict[str, int], scope: WorkspaceScope, hide: bool
) -> tuple[WorkspaceMetric, ...]:
    return tuple(
        _metric(key, label, values[key], scope, period, hide)
        for key, label, period in (
            ("headcount", "Headcount", "current"),
            ("assignable", "Assignable analysts", "current"),
            ("available_minutes", "Available capacity (minutes)", "next 7 days"),
            ("reserved_minutes", "Reserved capacity (minutes)", "next 7 days"),
            ("active_wip", "Active work", "current"),
            ("overdue", "Overdue work", "current"),
            ("blocked", "Blocked work", "current"),
        )
    )


def analytics_metrics(
    values: dict[str, int], scope: WorkspaceScope, hide: bool
) -> tuple[WorkspaceMetric, ...]:
    return tuple(
        _metric(key, label, values[key], scope, period, hide)
        for key, label, period in (
            ("demand", "Demand", "current"),
            ("completed_30d", "Completed work", "last 30 days"),
            ("average_age_hours", "Average work age (hours)", "active work"),
            ("overdue", "Overdue work", "current"),
            ("blocked", "Blocked work", "current"),
            ("blocked_minutes", "Blocked time (minutes)", "current blocked work"),
            ("available_minutes", "Forecast capacity (minutes)", "next 7 days"),
            ("reserved_minutes", "Reserved capacity (minutes)", "next 7 days"),
            ("reservation_accuracy", "Reservation coverage (%)", "active work"),
            ("handover_minutes", "Average handover elapsed time (minutes)", "last 30 days"),
            ("capability_gaps", "Capability gaps", "current"),
        )
    )


def _metric(
    key: str, label: str, value: int, scope: WorkspaceScope, period: str, hide: bool
) -> WorkspaceMetric:
    return WorkspaceMetric(
        key, label, None if hide else value, "<5" if hide else str(value), scope, period, hide
    )


_METRICS = """
WITH members AS (
 SELECT DISTINCT m.user_id,m.assignment_eligible FROM team_memberships m
 JOIN identity_account_projection a ON a.user_id=m.user_id AND a.is_active
 WHERE m.unit_id=ANY(CAST(:units AS uuid[])) AND m.state='active' AND m.valid_from<=:at
  AND (m.valid_until IS NULL OR :at<m.valid_until)
), patterns AS (
 SELECT p.user_id,(p.monday_minutes+p.tuesday_minutes+p.wednesday_minutes+
 p.thursday_minutes+p.friday_minutes+p.saturday_minutes+p.sunday_minutes) minutes
 FROM working_patterns p JOIN members m ON m.user_id=p.user_id WHERE p.valid_from<=:at
 AND (p.valid_until IS NULL OR :at<p.valid_until)
), work AS (
 SELECT count(*) FILTER (WHERE state IN ('pending','ready')) demand,
 count(*) FILTER (WHERE state IN ('ready','in_progress','blocked')) active_wip,
 count(*) FILTER (WHERE state='blocked') blocked,
 count(*) FILTER (WHERE state NOT IN ('complete','cancelled') AND due_at<:at) overdue,
 count(*) FILTER (WHERE state='complete' AND updated_at>=:at-interval '30 days') completed_30d,
 COALESCE(avg(EXTRACT(epoch FROM (:at-created_at))/3600)
  FILTER (WHERE state IN ('ready','in_progress','blocked')),0) average_age_hours,
 COALESCE(sum(EXTRACT(epoch FROM (:at-updated_at))/60)
  FILTER (WHERE state='blocked'),0) blocked_minutes,
 COALESCE(sum(remaining_minutes)
  FILTER (WHERE state IN ('ready','in_progress','blocked')),0) remaining_minutes
 FROM canonical_work_packages WHERE owning_unit_id=ANY(CAST(:units AS uuid[]))
), reserved AS (
 SELECT COALESCE(sum(reserved_minutes),0) minutes FROM capacity_reservations
 WHERE user_id IN (SELECT user_id FROM members) AND state IN ('held','active')
 AND starts_at<:at+interval '7 days' AND ends_at>:at
), handovers AS (
 SELECT COALESCE(avg(EXTRACT(epoch FROM (h.occurred_at-p.created_at))/60),0) minutes
 FROM work_package_handover_commands h
 JOIN canonical_work_packages p ON p.package_id=h.package_id
 WHERE p.owning_unit_id=ANY(CAST(:units AS uuid[]))
 AND h.occurred_at>=:at-interval '30 days'
), gaps AS (
 SELECT count(*) gaps FROM team_capability_coverage c JOIN team_delivery_profiles p
 ON p.profile_id=c.profile_id WHERE p.unit_id=ANY(CAST(:units AS uuid[])) AND p.is_active
 AND c.valid_from<=:at AND (c.valid_until IS NULL OR :at<c.valid_until)
 AND NOT EXISTS (SELECT 1 FROM members m JOIN assignment_competencies a ON a.user_id=m.user_id
 WHERE a.capability_id=c.capability_id AND a.proficiency>=c.proficiency
 AND (a.expires_at IS NULL OR :at<a.expires_at))
)
SELECT (SELECT count(*) FROM members) headcount,
 (SELECT count(*) FROM members WHERE assignment_eligible) assignable,
 COALESCE((SELECT sum(minutes) FROM patterns),0) available_minutes,
 (SELECT minutes FROM reserved) reserved_minutes,work.active_wip,work.blocked,work.overdue,
 work.demand,work.completed_30d,work.average_age_hours,work.blocked_minutes,
 CASE WHEN work.remaining_minutes=0 THEN 100 ELSE LEAST(100,
  ((SELECT minutes FROM reserved)*100/work.remaining_minutes)) END reservation_accuracy,
 (SELECT minutes FROM handovers) handover_minutes,
 (SELECT gaps FROM gaps) capability_gaps FROM work
"""
