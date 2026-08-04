"""Conflict-first inspection for the synthetic organisation fixture."""

from decimal import Decimal
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Connection

from coeus.domain.organisation import ManagementAction
from coeus.domain.synthetic_organisation_fixture import (
    SyntheticFixtureCounts,
    SyntheticFixtureFinding,
    SyntheticFixturePreview,
    SyntheticFixtureUser,
    fixture_preview_hash,
)
from coeus.persistence.synthetic_fixture_calendar_inspection import inspect_calendar_events
from coeus.persistence.synthetic_fixture_capability_inspection import (
    inspect_competencies,
    inspect_team_capabilities,
)
from coeus.persistence.synthetic_fixture_capacity import inspect_capacity_reservations
from coeus.persistence.synthetic_fixture_grant_inspection import (
    inspect_management_grants,
    inspect_service_grants,
)
from coeus.persistence.synthetic_fixture_inspection_common import (
    classify,
    finding,
    material,
    row,
    zero_counts,
)
from coeus.persistence.synthetic_fixture_plan import SyntheticFixturePlan
from coeus.persistence.synthetic_fixture_task_inspection import inspect_tasks
from coeus.persistence.synthetic_fixture_values import (
    MANIFEST_VERSION,
    PROVENANCE,
    TIME_ZONE,
    UNIT_DESCRIPTION,
    delivery_profile_id,
    fixture_grant_id,
)
from coeus.persistence.synthetic_fixture_workforce_inspection import (
    inspect_memberships,
    inspect_patterns,
)
from coeus.repositories.synthetic_organisation_manifest import (
    BASELINE,
    SyntheticUnitSpec,
    synthetic_unit_specs,
)


def inspect_fixture(
    connection: Connection,
    actor_user_id: UUID,
    users: tuple[SyntheticFixtureUser, ...],
) -> SyntheticFixturePlan:
    findings: list[SyntheticFixtureFinding] = []
    state: list[object] = []
    creates = zero_counts()
    unchanged = zero_counts()
    user_map = {user.username.casefold(): user for user in users}
    units = synthetic_unit_specs()
    root = units[0]
    foreign_roots = tuple(
        connection.execute(
            text(
                "SELECT unit_id,name FROM organisation_units "
                "WHERE parent_unit_id IS NULL AND is_active ORDER BY unit_id"
            )
        ).mappings()
    )
    state.append(("roots", tuple(material(item) for item in foreign_roots)))
    if any(UUID(str(item["unit_id"])) != root.unit_id for item in foreign_roots):
        findings.append(
            finding("foreign_root", "unit", root.key, "A different active root exists.")
        )

    missing_units = _inspect_units(connection, units, findings, state, creates, unchanged)
    missing_profiles = _inspect_profiles(connection, units, findings, state, creates, unchanged)
    missing_memberships = inspect_memberships(
        connection, user_map, findings, state, creates, unchanged
    )
    missing_patterns = inspect_patterns(connection, user_map, findings, state, creates, unchanged)
    missing_grants = _inspect_grants(
        connection, actor_user_id, root, findings, state, creates, unchanged
    )
    missing_team_capabilities = inspect_team_capabilities(
        connection, findings, state, creates, unchanged
    )
    missing_competencies = inspect_competencies(
        connection,
        user_map,
        findings,
        state,
        creates,
        unchanged,
    )
    missing_calendar_events = inspect_calendar_events(
        connection,
        user_map,
        findings,
        state,
        creates,
        unchanged,
    )
    missing_management_grants = inspect_management_grants(
        connection,
        user_map,
        findings,
        state,
        creates,
        unchanged,
    )
    missing_service_grants = inspect_service_grants(connection, findings, state, creates, unchanged)
    missing_tasks, missing_task_ownership, missing_work_packages = inspect_tasks(
        connection,
        user_map,
        findings,
        state,
        creates,
        unchanged,
    )
    missing_capacity_reservations = inspect_capacity_reservations(
        connection, user_map, findings, state, creates, unchanged
    )
    marker = (
        connection.execute(text("SELECT * FROM organisation_bootstrap_state WHERE singleton=true"))
        .mappings()
        .first()
    )
    state.append(("bootstrap", material(marker)))
    if marker is not None and UUID(str(marker["root_unit_id"])) != root.unit_id:
        findings.append(
            finding(
                "bootstrap_root_mismatch",
                "bootstrap",
                "root",
                "Bootstrap owns another root.",
            )
        )
    preview = SyntheticFixturePreview(
        MANIFEST_VERSION,
        fixture_preview_hash(actor_user_id, MANIFEST_VERSION, state),
        SyntheticFixtureCounts(**creates),
        SyntheticFixtureCounts(**unchanged),
        tuple(findings),
    )
    return SyntheticFixturePlan(
        preview,
        tuple(missing_units),
        tuple(missing_profiles),
        tuple(missing_memberships),
        tuple(missing_patterns),
        tuple(missing_grants),
        tuple(missing_team_capabilities),
        tuple(missing_competencies),
        tuple(missing_calendar_events),
        tuple(missing_management_grants),
        tuple(missing_service_grants),
        tuple(missing_tasks),
        tuple(missing_task_ownership),
        tuple(missing_work_packages),
        tuple(missing_capacity_reservations),
        marker is None,
    )


def _inspect_units(
    connection: Connection,
    specs: tuple[SyntheticUnitSpec, ...],
    findings: list[SyntheticFixtureFinding],
    state: list[object],
    creates: dict[str, int],
    unchanged: dict[str, int],
) -> list[SyntheticUnitSpec]:
    by_key = {item.key: item for item in specs}
    missing: list[SyntheticUnitSpec] = []
    for spec in specs:
        existing = row(connection, "organisation_units", "unit_id", spec.unit_id)
        state.append(("unit", spec.key, material(existing)))
        expected = {
            "name": spec.name,
            "short_name": spec.short_name,
            "category": spec.category.value,
            "parent_unit_id": by_key[spec.parent_key].unit_id if spec.parent_key else None,
            "is_active": True,
            "valid_from": BASELINE,
            "valid_until": None,
            "time_zone": TIME_ZONE,
            "description": UNIT_DESCRIPTION,
            "provenance": PROVENANCE,
            "version": 1,
        }
        if existing is not None and existing["provenance"] != PROVENANCE:
            findings.append(
                finding(
                    "fixture_identifier_collision",
                    "unit",
                    spec.key,
                    "Stable fixture identity is owned by a non-fixture row.",
                )
            )
            continue
        if existing is not None and any(
            existing[field] != expected[field]
            for field in (
                "category",
                "parent_unit_id",
                "is_active",
                "valid_from",
                "valid_until",
                "version",
            )
        ):
            findings.append(
                finding(
                    "fixture_structural_drift",
                    "unit",
                    spec.key,
                    "Synthetic unit structure requires explicit lifecycle recovery.",
                )
            )
            continue
        classify(
            existing,
            expected,
            spec,
            "units",
            findings,
            missing,
            creates,
            unchanged,
        )
    return missing


def _inspect_profiles(
    connection: Connection,
    specs: tuple[SyntheticUnitSpec, ...],
    findings: list[SyntheticFixtureFinding],
    state: list[object],
    creates: dict[str, int],
    unchanged: dict[str, int],
) -> list[SyntheticUnitSpec]:
    missing: list[SyntheticUnitSpec] = []
    for spec in (item for item in specs if item.route is not None):
        assert spec.route is not None
        existing = row(
            connection,
            "team_delivery_profiles",
            "profile_id",
            delivery_profile_id(spec.unit_id),
        )
        by_unit = row(connection, "team_delivery_profiles", "unit_id", spec.unit_id)
        state.append(("profile", spec.key, material(existing), material(by_unit)))
        if existing is None and by_unit is not None:
            findings.append(
                finding(
                    "profile_collision",
                    "delivery_profile",
                    spec.key,
                    "Unit has a local profile.",
                )
            )
            continue
        expected = {
            "unit_id": spec.unit_id,
            "route": spec.route.value,
            "wip_limit": spec.wip_limit,
            "weekly_hours": Decimal("40.00"),
            "policy_version": 1,
            "is_active": True,
            "provenance": PROVENANCE,
        }
        if existing is not None and existing["provenance"] != PROVENANCE:
            findings.append(
                finding(
                    "fixture_identifier_collision",
                    "delivery_profile",
                    spec.key,
                    "Stable fixture identity is owned by a non-fixture row.",
                )
            )
            continue
        classify(
            existing,
            expected,
            spec,
            "delivery_profiles",
            findings,
            missing,
            creates,
            unchanged,
        )
    return missing


def _inspect_grants(
    connection: Connection,
    actor_user_id: UUID,
    root: SyntheticUnitSpec,
    findings: list[SyntheticFixtureFinding],
    state: list[object],
    creates: dict[str, int],
    unchanged: dict[str, int],
) -> list[ManagementAction]:
    missing: list[ManagementAction] = []
    for action in ManagementAction:
        existing = row(
            connection,
            "team_management_grants",
            "grant_id",
            fixture_grant_id(action),
        )
        state.append(("grant", action.value, material(existing)))
        expected = {
            "root_unit_id": root.unit_id,
            "action": action.value,
            "include_descendants": True,
            "valid_until": None,
            "revoked_at": None,
            "source_grant_id": None,
            "delegation_depth": 0,
            "version": 1,
        }
        classify(
            existing,
            expected,
            action,
            "grants",
            findings,
            missing,
            creates,
            unchanged,
        )
    return missing
