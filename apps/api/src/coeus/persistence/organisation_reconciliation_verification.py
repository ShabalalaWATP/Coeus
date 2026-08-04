"""Checks that a completed shadow checkpoint still describes stored state."""

from sqlalchemy import text
from sqlalchemy.engine import Connection

from coeus.domain.organisation_reconciliation import OrganisationReconciliationPlan


def projection_matches(connection: Connection, plan: OrganisationReconciliationPlan) -> bool:
    """Return false when authority-owned shadow rows have drifted."""
    for unit, _revision in plan.units:
        if not _matches(
            connection,
            """
            SELECT 1 FROM organisation_units WHERE unit_id=:unit_id AND name=:name
              AND short_name=:short_name AND category=:category
              AND parent_unit_id IS NOT DISTINCT FROM :parent_unit_id
              AND is_active=:is_active AND valid_from=:valid_from
              AND valid_until IS NOT DISTINCT FROM :valid_until
              AND time_zone=:time_zone AND description=:description
              AND provenance=:provenance
            """,
            vars(unit),
        ):
            return False
    for profile in plan.delivery_profiles:
        if not _matches(
            connection,
            """
            SELECT 1 FROM team_delivery_profiles WHERE profile_id=:profile_id
              AND unit_id=:unit_id AND route=:route AND wip_limit=:wip_limit
              AND weekly_hours=:weekly_hours AND is_active=:is_active
              AND provenance=:provenance
            """,
            _enum_params(profile),
        ):
            return False
    for coverage in plan.capability_coverage:
        if not _matches(
            connection,
            """
            SELECT 1 FROM team_capability_coverage WHERE coverage_id=:coverage_id
              AND profile_id=:profile_id AND capability_id=:capability_id
              AND proficiency=:proficiency AND valid_from=:valid_from
              AND valid_until IS NOT DISTINCT FROM :valid_until
              AND approved_by_user_id=:approved_by_user_id
            """,
            vars(coverage),
        ):
            return False
    for membership in plan.memberships:
        if not _matches(
            connection,
            """
            SELECT 1 FROM team_memberships WHERE membership_id=:membership_id
              AND user_id=:user_id AND unit_id=:unit_id AND role=:role AND state=:state
              AND assignment_eligible=:assignment_eligible
              AND created_by_user_id=:created_by_user_id AND reason=:reason
              AND provenance=:provenance AND valid_until IS NOT DISTINCT FROM :valid_until
            """,
            _enum_params(membership),
        ):
            return False
    if _has_extra_source_rows(connection, plan):
        return False
    present = [item.membership_id for item in plan.memberships]
    extra_membership = connection.execute(
        text(
            "SELECT 1 FROM team_memberships WHERE provenance=:provenance "
            "AND state IN ('active','suspended') "
            "AND NOT (membership_id = ANY(CAST(:present AS uuid[]))) LIMIT 1"
        ),
        {"provenance": plan.checkpoint.source_namespace, "present": present},
    ).first()
    return extra_membership is None


def _has_extra_source_rows(connection: Connection, plan: OrganisationReconciliationPlan) -> bool:
    unit_ids = [unit.unit_id for unit, _revision in plan.units]
    profile_ids = [profile.profile_id for profile in plan.delivery_profiles]
    params = {
        "provenance": plan.checkpoint.source_namespace,
        "unit_ids": unit_ids,
        "profile_ids": profile_ids,
    }
    return (
        connection.execute(
            text(
                "SELECT 1 FROM organisation_units WHERE provenance=:provenance AND is_active "
                "AND NOT (unit_id = ANY(CAST(:unit_ids AS uuid[]))) "
                "UNION ALL SELECT 1 FROM team_delivery_profiles "
                "WHERE provenance=:provenance AND is_active "
                "AND NOT (profile_id = ANY(CAST(:profile_ids AS uuid[]))) LIMIT 1"
            ),
            params,
        ).first()
        is not None
    )


def _matches(connection: Connection, statement: str, params: dict[str, object]) -> bool:
    return connection.execute(text(statement), params).first() is not None


def _enum_params(value: object) -> dict[str, object]:
    return {key: getattr(item, "value", item) for key, item in vars(value).items()}
