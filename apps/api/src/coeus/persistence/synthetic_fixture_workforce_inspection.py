"""Membership and working-pattern inspection for the synthetic fixture."""

from collections.abc import Mapping
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Connection

from coeus.domain.organisation import MembershipState
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
from coeus.persistence.synthetic_fixture_values import (
    MEMBERSHIP_REASON,
    PROVENANCE,
    TIME_ZONE,
)
from coeus.repositories.synthetic_organisation_manifest import (
    SyntheticPostingSpec,
    SyntheticWorkingPatternSpec,
    synthetic_posting_specs,
    synthetic_unit_specs,
    synthetic_working_patterns,
)


def inspect_memberships(
    connection: Connection,
    users: Mapping[str, SyntheticFixtureUser],
    findings: list[SyntheticFixtureFinding],
    state: list[object],
    creates: dict[str, int],
    unchanged: dict[str, int],
) -> list[SyntheticPostingSpec]:
    units = {item.key: item for item in synthetic_unit_specs()}
    missing: list[SyntheticPostingSpec] = []
    for spec in synthetic_posting_specs():
        user = users.get(spec.username.casefold())
        if user is None:
            findings.append(
                finding("missing_user", "membership", spec.username, "Seed identity is missing.")
            )
            continue
        if spec.state is MembershipState.ACTIVE and not user.is_active:
            findings.append(
                finding(
                    "inactive_user",
                    "membership",
                    spec.username,
                    "Active posting has an inactive user.",
                )
            )
        existing = row(connection, "team_memberships", "membership_id", spec.membership_id)
        overlaps = _membership_overlaps(connection, spec, user.user_id)
        state.append(
            (
                "membership",
                spec.username,
                material(existing),
                tuple(material(item) for item in overlaps),
            )
        )
        if existing is None and overlaps:
            findings.append(
                finding(
                    "posting_overlap",
                    "membership",
                    spec.username,
                    "A local posting overlaps this fixture posting.",
                )
            )
            continue
        if existing is not None and existing["provenance"] != PROVENANCE:
            findings.append(
                finding(
                    "fixture_identifier_collision",
                    "membership",
                    spec.username,
                    "Stable fixture identity is owned by a non-fixture row.",
                )
            )
            continue
        expected = {
            "user_id": user.user_id,
            "unit_id": units[spec.unit_key].unit_id,
            "role": spec.role.value,
            "state": spec.state.value,
            "assignment_eligible": spec.assignment_eligible,
            "valid_from": spec.valid_from,
            "valid_until": spec.valid_until,
            "reason": MEMBERSHIP_REASON,
            "provenance": PROVENANCE,
            "version": 1,
        }
        classify(
            existing,
            expected,
            spec,
            "memberships",
            findings,
            missing,
            creates,
            unchanged,
        )
    return missing


def inspect_patterns(
    connection: Connection,
    users: Mapping[str, SyntheticFixtureUser],
    findings: list[SyntheticFixtureFinding],
    state: list[object],
    creates: dict[str, int],
    unchanged: dict[str, int],
) -> list[SyntheticWorkingPatternSpec]:
    missing: list[SyntheticWorkingPatternSpec] = []
    for spec in synthetic_working_patterns():
        user = users.get(spec.username.casefold())
        if user is None:
            continue
        existing = row(connection, "working_patterns", "pattern_id", spec.pattern_id)
        overlaps = _pattern_overlaps(connection, spec, user.user_id)
        state.append(
            (
                "pattern",
                spec.username,
                material(existing),
                tuple(material(item) for item in overlaps),
            )
        )
        if existing is None and overlaps:
            findings.append(
                finding(
                    "pattern_overlap",
                    "working_pattern",
                    spec.username,
                    "A local working pattern overlaps.",
                )
            )
            continue
        if existing is not None and existing["provenance"] != PROVENANCE:
            findings.append(
                finding(
                    "fixture_identifier_collision",
                    "working_pattern",
                    spec.username,
                    "Stable fixture identity is owned by a non-fixture row.",
                )
            )
            continue
        classify(
            existing,
            _pattern_expected(spec, user.user_id),
            spec,
            "working_patterns",
            findings,
            missing,
            creates,
            unchanged,
        )
    return missing


def _membership_overlaps(
    connection: Connection,
    spec: SyntheticPostingSpec,
    user_id: UUID,
) -> tuple[Any, ...]:
    return tuple(
        connection.execute(
            text(
                "SELECT membership_id,unit_id,state,valid_from,valid_until "
                "FROM team_memberships WHERE user_id=:user_id "
                "AND membership_id<>:membership_id AND state<>'cancelled' "
                "AND tstzrange(valid_from,valid_until,'[)') && "
                "tstzrange(:valid_from,:valid_until,'[)') ORDER BY membership_id"
            ),
            {
                "user_id": user_id,
                "membership_id": spec.membership_id,
                "valid_from": spec.valid_from,
                "valid_until": spec.valid_until,
            },
        ).mappings()
    )


def _pattern_overlaps(
    connection: Connection,
    spec: SyntheticWorkingPatternSpec,
    user_id: UUID,
) -> tuple[Any, ...]:
    return tuple(
        connection.execute(
            text(
                "SELECT pattern_id,valid_from,valid_until FROM working_patterns "
                "WHERE user_id=:user_id AND pattern_id<>:pattern_id AND "
                "tstzrange(valid_from,valid_until,'[)') && "
                "tstzrange(:valid_from,NULL,'[)')"
            ),
            {
                "user_id": user_id,
                "pattern_id": spec.pattern_id,
                "valid_from": spec.valid_from,
            },
        ).mappings()
    )


def _pattern_expected(
    spec: SyntheticWorkingPatternSpec,
    user_id: UUID,
) -> dict[str, Any]:
    weekdays = ("monday", "tuesday", "wednesday", "thursday", "friday")
    return {
        "user_id": user_id,
        "time_zone": TIME_ZONE,
        **{f"{day}_minutes": spec.weekday_minutes for day in weekdays},
        "saturday_minutes": 0,
        "sunday_minutes": 0,
        "valid_from": spec.valid_from,
        "valid_until": None,
        "version": 1,
        "provenance": PROVENANCE,
    }
