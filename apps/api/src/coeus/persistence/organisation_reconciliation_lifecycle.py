"""Version and effective-lifecycle helpers for shadow reconciliation."""

from dataclasses import replace
from datetime import datetime
from enum import StrEnum
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import text
from sqlalchemy.engine import Connection, RowMapping

from coeus.domain.organisation import TeamMembership
from coeus.domain.organisation_reconciliation import OrganisationReconciliationPlan

_VERSION_TARGETS = {
    ("organisation_units", "unit_id", "version"): (
        "SELECT * FROM organisation_units WHERE unit_id=:unit_id FOR UPDATE",
        (
            "name",
            "short_name",
            "category",
            "parent_unit_id",
            "is_active",
            "valid_from",
            "valid_until",
            "time_zone",
            "description",
            "provenance",
        ),
    ),
    ("team_delivery_profiles", "profile_id", "policy_version"): (
        "SELECT * FROM team_delivery_profiles WHERE profile_id=:profile_id FOR UPDATE",
        ("unit_id", "route", "wip_limit", "weekly_hours", "is_active", "provenance"),
    ),
    ("team_capability_coverage", "coverage_id", "policy_version"): (
        "SELECT * FROM team_capability_coverage WHERE coverage_id=:coverage_id FOR UPDATE",
        (
            "profile_id",
            "capability_id",
            "proficiency",
            "valid_from",
            "valid_until",
            "approved_by_user_id",
        ),
    ),
}


def versioned_upsert(
    connection: Connection,
    statement: str,
    value: object,
    label: str,
    table_name: str,
    identity_field: str,
    version_field: str,
) -> None:
    params = _params(value)
    params[version_field] = next_version(
        connection,
        table_name,
        identity_field,
        params[identity_field],
        version_field,
        params,
    )
    if connection.execute(text(statement), params).first() is None:
        raise ValueError(f"{label} identity or version conflicts with stored state")


def next_version(
    connection: Connection,
    table_name: str,
    identity_field: str,
    identity: object,
    version_field: str,
    desired: dict[str, object],
) -> int:
    target = _VERSION_TARGETS.get((table_name, identity_field, version_field))
    if target is None:
        raise ValueError("unsupported reconciliation version target")
    query, material_fields = target
    row = connection.execute(text(query), {identity_field: identity}).mappings().first()
    if row is None:
        return 1
    current = int(str(row[version_field]))
    return current if _same_values(row, desired, material_fields) else current + 1


def end_absent_coverage(connection: Connection, plan: OrganisationReconciliationPlan) -> None:
    profile_ids = [item.profile_id for item in plan.delivery_profiles]
    present = [item.coverage_id for item in plan.capability_coverage]
    invalid = connection.execute(
        text(
            "SELECT 1 FROM team_capability_coverage coverage "
            "JOIN team_delivery_profiles profile ON profile.profile_id=coverage.profile_id "
            "WHERE profile.provenance=:provenance AND coverage.valid_until IS NULL "
            "AND coverage.valid_from >= :effective_at "
            "AND (NOT (profile.profile_id = ANY(CAST(:profile_ids AS uuid[]))) OR "
            "NOT (coverage.coverage_id = ANY(CAST(:present AS uuid[])))) LIMIT 1"
        ),
        {
            "effective_at": plan.effective_at,
            "profile_ids": profile_ids,
            "present": present,
            "provenance": plan.checkpoint.source_namespace,
        },
    ).first()
    if invalid is not None:
        raise ValueError("absent capability coverage cannot end before its start")
    connection.execute(
        text(
            "UPDATE team_capability_coverage coverage SET valid_until=:effective_at "
            "FROM team_delivery_profiles profile "
            "WHERE profile.profile_id=coverage.profile_id "
            "AND profile.provenance=:provenance AND coverage.valid_until IS NULL "
            "AND (NOT (profile.profile_id = ANY(CAST(:profile_ids AS uuid[]))) OR "
            "NOT (coverage.coverage_id = ANY(CAST(:present AS uuid[]))))"
        ),
        {
            "effective_at": plan.effective_at,
            "profile_ids": profile_ids,
            "present": present,
            "provenance": plan.checkpoint.source_namespace,
        },
    )


def deactivate_absent_teams(connection: Connection, plan: OrganisationReconciliationPlan) -> None:
    """Retire only source-owned profiles and units omitted from the latest snapshot."""
    present_units = [unit.unit_id for unit, _revision in plan.units]
    connection.execute(
        text(
            "UPDATE team_delivery_profiles SET is_active=false, "
            "policy_version=policy_version + 1, updated_at=now() "
            "WHERE provenance=:provenance AND is_active "
            "AND NOT (unit_id = ANY(CAST(:present_units AS uuid[])))"
        ),
        {"provenance": plan.checkpoint.source_namespace, "present_units": present_units},
    )
    connection.execute(
        text(
            "UPDATE organisation_units SET is_active=false, version=version + 1, "
            "updated_at=now() WHERE provenance=:provenance AND is_active "
            "AND NOT (unit_id = ANY(CAST(:present_units AS uuid[])))"
        ),
        {"provenance": plan.checkpoint.source_namespace, "present_units": present_units},
    )


def resolve_membership_identities(
    connection: Connection,
    memberships: tuple[TeamMembership, ...],
    effective_at: datetime,
) -> tuple[TeamMembership, ...]:
    resolved: list[TeamMembership] = []
    for membership in memberships:
        candidate_id = membership.membership_id
        for _depth in range(32):
            row = (
                connection.execute(
                    text(
                        "SELECT state, valid_until FROM team_memberships "
                        "WHERE membership_id=:membership_id FOR UPDATE"
                    ),
                    {"membership_id": candidate_id},
                )
                .mappings()
                .first()
            )
            if row is None or row["state"] not in {"ended", "cancelled"}:
                break
            valid_until = row["valid_until"]
            if valid_until is None:
                raise ValueError("a terminal membership is missing its end time")
            candidate_id = uuid5(
                NAMESPACE_URL,
                f"coeus:organisation:posting:{candidate_id}:{valid_until.isoformat()}",
            )
        else:
            raise ValueError("membership posting history exceeds the supported depth")
        resolved.append(
            replace(
                membership,
                membership_id=candidate_id,
                valid_from=(
                    membership.valid_from
                    if candidate_id == membership.membership_id
                    else effective_at
                ),
            )
        )
    return tuple(resolved)


def _params(value: object) -> dict[str, object]:
    return {
        key: item.value if isinstance(item, StrEnum) else item for key, item in vars(value).items()
    }


def _same_values(row: RowMapping, desired: dict[str, object], fields: tuple[str, ...]) -> bool:
    return all(str(row[field]) == str(desired[field]) for field in fields)
