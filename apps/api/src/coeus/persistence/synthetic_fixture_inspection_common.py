"""Shared helpers for deterministic synthetic fixture inspection."""

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Connection, RowMapping

from coeus.domain.synthetic_organisation_fixture import SyntheticFixtureFinding

_ROW_QUERIES = {
    ("organisation_units", "unit_id"): "SELECT * FROM organisation_units WHERE unit_id=:value",
    ("team_delivery_profiles", "profile_id"): (
        "SELECT * FROM team_delivery_profiles WHERE profile_id=:value"
    ),
    ("team_delivery_profiles", "unit_id"): (
        "SELECT * FROM team_delivery_profiles WHERE unit_id=:value"
    ),
    ("team_memberships", "membership_id"): (
        "SELECT * FROM team_memberships WHERE membership_id=:value"
    ),
    ("working_patterns", "pattern_id"): ("SELECT * FROM working_patterns WHERE pattern_id=:value"),
    ("team_management_grants", "grant_id"): (
        "SELECT * FROM team_management_grants WHERE grant_id=:value"
    ),
    ("team_capability_coverage", "coverage_id"): (
        "SELECT * FROM team_capability_coverage WHERE coverage_id=:value"
    ),
    ("assignment_competencies", "competency_id"): (
        "SELECT * FROM assignment_competencies WHERE competency_id=:value"
    ),
    ("calendar_events", "event_id"): "SELECT * FROM calendar_events WHERE event_id=:value",
    ("coeus_ticket_aggregates", "ticket_id"): (
        "SELECT * FROM coeus_ticket_aggregates WHERE ticket_id=:value"
    ),
    ("team_task_ownership", "ownership_id"): (
        "SELECT * FROM team_task_ownership WHERE ownership_id=:value"
    ),
    ("canonical_work_packages", "package_id"): (
        "SELECT * FROM canonical_work_packages WHERE package_id=:value"
    ),
    ("capacity_reservations", "reservation_id"): (
        "SELECT * FROM capacity_reservations WHERE reservation_id=:value"
    ),
}


def classify(
    row: RowMapping | None,
    expected: dict[str, Any],
    spec: Any,
    bucket: str,
    findings: list[SyntheticFixtureFinding],
    missing: list[Any],
    creates: dict[str, int],
    unchanged: dict[str, int],
) -> None:
    key = getattr(spec, "key", getattr(spec, "username", getattr(spec, "value", str(spec))))
    if row is None:
        missing.append(spec)
        creates[bucket] += 1
    elif all(row[field] == value for field, value in expected.items()):
        unchanged[bucket] += 1
    else:
        findings.append(
            finding(
                "fixture_row_changed",
                bucket.rstrip("s"),
                str(key),
                "Existing synthetic row differs from the manifest.",
            )
        )


def row(
    connection: Connection,
    table: str,
    key: str,
    value: UUID,
) -> RowMapping | None:
    query = _ROW_QUERIES.get((table, key))
    if query is None:
        raise ValueError("unsupported fixture inspection table")
    return connection.execute(text(query), {"value": value}).mappings().first()


def material(value: RowMapping | None) -> object:
    if value is None:
        return None
    return tuple(
        (
            key,
            str(item) if isinstance(item, (UUID, datetime, Decimal)) else item,
        )
        for key, item in sorted(value.items())
    )


def zero_counts() -> dict[str, int]:
    return {
        "units": 0,
        "delivery_profiles": 0,
        "memberships": 0,
        "working_patterns": 0,
        "grants": 0,
        "team_capabilities": 0,
        "competencies": 0,
        "calendar_events": 0,
        "tasks": 0,
        "task_ownership": 0,
        "work_packages": 0,
        "capacity_reservations": 0,
    }


def finding(
    code: str,
    entity_type: str,
    key: str,
    message: str,
) -> SyntheticFixtureFinding:
    return SyntheticFixtureFinding(code, entity_type, key, message)
