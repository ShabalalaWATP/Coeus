"""Calendar scenario inspection for the synthetic organisation fixture."""

from collections.abc import Mapping

from sqlalchemy import text
from sqlalchemy.engine import Connection

from coeus.domain.synthetic_organisation_fixture import (
    SyntheticFixtureFinding,
    SyntheticFixtureUser,
)
from coeus.persistence.synthetic_fixture_inspection_common import (
    classify,
    finding,
    material,
    row,
)
from coeus.persistence.synthetic_fixture_values import PROVENANCE, TIME_ZONE
from coeus.repositories.synthetic_calendar_manifest import (
    SyntheticCalendarEventSpec,
    synthetic_calendar_events,
)
from coeus.repositories.synthetic_organisation_manifest import synthetic_unit_specs


def inspect_calendar_events(
    connection: Connection,
    users: Mapping[str, SyntheticFixtureUser],
    findings: list[SyntheticFixtureFinding],
    state: list[object],
    creates: dict[str, int],
    unchanged: dict[str, int],
) -> list[SyntheticCalendarEventSpec]:
    units = {item.key: item for item in synthetic_unit_specs()}
    missing: list[SyntheticCalendarEventSpec] = []
    for spec in synthetic_calendar_events():
        owner = users.get(spec.owner_username.casefold())
        creator = users.get(spec.created_by_username.casefold())
        if owner is None or creator is None:
            findings.append(
                finding(
                    "calendar_user_missing",
                    "calendar_event",
                    spec.key,
                    "Calendar owner or creator identity is missing.",
                )
            )
            continue
        existing = row(connection, "calendar_events", "event_id", spec.event_id)
        dependants = (
            connection.execute(
                text(
                    "SELECT "
                    "(SELECT count(*) FROM calendar_event_scopes WHERE event_id=:event_id) scopes,"
                    "(SELECT count(*) FROM calendar_event_versions "
                    "WHERE event_id=:event_id) versions,"
                    "(SELECT count(*) FROM calendar_event_commands "
                    "WHERE event_id=:event_id) commands"
                ),
                {"event_id": spec.event_id},
            )
            .mappings()
            .one()
        )
        state.append(("calendar_event", spec.key, material(existing), material(dependants)))
        expected_scope_count = 2 if spec.manager_scope_unit_key else 1
        if existing is not None and (
            int(dependants["scopes"]) != expected_scope_count
            or int(dependants["versions"]) != 1
            or int(dependants["commands"]) != 1
        ):
            findings.append(
                finding(
                    "calendar_evidence_incomplete",
                    "calendar_event",
                    spec.key,
                    "Existing fixture event has incomplete canonical evidence.",
                )
            )
            continue
        expected = {
            "owner_user_id": owner.user_id,
            "source": spec.source.value,
            "activity_category": spec.activity.value,
            "starts_at": spec.starts_at,
            "ends_at": spec.ends_at,
            "all_day_start": spec.all_day_start,
            "all_day_end": spec.all_day_end,
            "time_zone": TIME_ZONE,
            "availability_effect": spec.availability.value,
            "privacy_level": spec.privacy.value,
            "note": "",
            "recurrence_rule": None,
            "status": "active",
            "manager_scope_unit_id": (
                units[spec.manager_scope_unit_key].unit_id if spec.manager_scope_unit_key else None
            ),
            "created_by_user_id": creator.user_id,
            "cancelled_at": None,
            "version": 1,
            "provenance": PROVENANCE,
        }
        classify(
            existing,
            expected,
            spec,
            "calendar_events",
            findings,
            missing,
            creates,
            unchanged,
        )
    return missing
