"""Narrow exact-identifier repair for mutable synthetic fixture rows."""

from sqlalchemy import text
from sqlalchemy.engine import Connection

from coeus.domain.synthetic_organisation_fixture import (
    SyntheticFixtureFinding,
    SyntheticFixtureUser,
)
from coeus.persistence.synthetic_fixture_values import (
    MEMBERSHIP_REASON,
    PROVENANCE,
    TIME_ZONE,
    UNIT_DESCRIPTION,
    delivery_profile_id,
)
from coeus.repositories.synthetic_organisation_manifest import (
    BASELINE,
    synthetic_posting_specs,
    synthetic_unit_specs,
    synthetic_working_patterns,
)

REPAIRABLE_ENTITIES = frozenset({"unit", "delivery_profile", "membership", "working_pattern"})


def can_reconcile(findings: tuple[SyntheticFixtureFinding, ...]) -> bool:
    return bool(findings) and all(
        item.code == "fixture_row_changed" and item.entity_type in REPAIRABLE_ENTITIES
        for item in findings
    )


def reconcile_exact_fixture_rows(
    connection: Connection,
    users: dict[str, SyntheticFixtureUser],
) -> None:
    units = {item.key: item for item in synthetic_unit_specs()}
    for spec in units.values():
        parent_id = units[spec.parent_key].unit_id if spec.parent_key else None
        connection.execute(
            text(
                "UPDATE organisation_units SET name=:name,short_name=:short_name,"
                "category=:category,"
                "parent_unit_id=:parent_id,is_active=true,valid_from=:valid_from,valid_until=NULL,"
                "time_zone=:time_zone,description=:description,provenance=:provenance,version=1 "
                "WHERE unit_id=:unit_id"
            ),
            {
                "unit_id": spec.unit_id,
                "name": spec.name,
                "short_name": spec.short_name,
                "category": spec.category.value,
                "parent_id": parent_id,
                "valid_from": BASELINE,
                "time_zone": TIME_ZONE,
                "description": UNIT_DESCRIPTION,
                "provenance": PROVENANCE,
            },
        )
        if spec.route is not None:
            connection.execute(
                text(
                    "UPDATE team_delivery_profiles SET unit_id=:unit_id,route=:route,"
                    "wip_limit=:wip_limit,weekly_hours=40,policy_version=1,is_active=true,"
                    "provenance=:provenance WHERE profile_id=:profile_id"
                ),
                {
                    "profile_id": delivery_profile_id(spec.unit_id),
                    "unit_id": spec.unit_id,
                    "route": spec.route.value,
                    "wip_limit": spec.wip_limit,
                    "provenance": PROVENANCE,
                },
            )
    for posting in synthetic_posting_specs():
        connection.execute(
            text(
                "UPDATE team_memberships SET user_id=:user_id,unit_id=:unit_id,role=:role,"
                "state=:state,assignment_eligible=:eligible,valid_from=:valid_from,"
                "valid_until=:valid_until,reason=:reason,provenance=:provenance,version=1 "
                "WHERE membership_id=:membership_id"
            ),
            {
                "membership_id": posting.membership_id,
                "user_id": users[posting.username].user_id,
                "unit_id": units[posting.unit_key].unit_id,
                "role": posting.role.value,
                "state": posting.state.value,
                "eligible": posting.assignment_eligible,
                "valid_from": posting.valid_from,
                "valid_until": posting.valid_until,
                "reason": MEMBERSHIP_REASON,
                "provenance": PROVENANCE,
            },
        )
    for pattern in synthetic_working_patterns():
        connection.execute(
            text(
                "UPDATE working_patterns SET user_id=:user_id,time_zone=:time_zone,"
                "monday_minutes=:minutes,tuesday_minutes=:minutes,wednesday_minutes=:minutes,"
                "thursday_minutes=:minutes,friday_minutes=:minutes,saturday_minutes=0,"
                "sunday_minutes=0,valid_from=:valid_from,valid_until=NULL,version=1,"
                "provenance=:provenance "
                "WHERE pattern_id=:pattern_id"
            ),
            {
                "pattern_id": pattern.pattern_id,
                "user_id": users[pattern.username].user_id,
                "time_zone": TIME_ZONE,
                "minutes": pattern.weekday_minutes,
                "valid_from": pattern.valid_from,
                "provenance": PROVENANCE,
            },
        )
