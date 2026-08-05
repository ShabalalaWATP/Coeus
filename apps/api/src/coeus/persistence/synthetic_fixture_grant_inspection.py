"""Scoped manager-grant inspection for the synthetic fixture."""

from collections.abc import Mapping

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
from coeus.repositories.synthetic_grant_manifest import (
    SyntheticManagementGrantSpec,
    SyntheticServiceGrantSpec,
    synthetic_management_grants,
    synthetic_service_grants,
)
from coeus.repositories.synthetic_organisation_manifest import BASELINE, synthetic_unit_specs


def inspect_management_grants(
    connection: Connection,
    users: Mapping[str, SyntheticFixtureUser],
    findings: list[SyntheticFixtureFinding],
    state: list[object],
    creates: dict[str, int],
    unchanged: dict[str, int],
) -> list[SyntheticManagementGrantSpec]:
    units = {item.key: item for item in synthetic_unit_specs()}
    missing: list[SyntheticManagementGrantSpec] = []
    for spec in synthetic_management_grants():
        manager = users.get(spec.username.casefold())
        if manager is None or not manager.is_active:
            findings.append(
                finding(
                    "management_grant_user_unavailable",
                    "grant",
                    spec.key,
                    "Scoped manager identity is missing or inactive.",
                )
            )
            continue
        existing = row(
            connection,
            "team_management_grants",
            "grant_id",
            spec.grant_id,
        )
        state.append(("management_grant", spec.key, material(existing)))
        expected = {
            "manager_user_id": manager.user_id,
            "root_unit_id": units[spec.unit_key].unit_id,
            "action": spec.action.value,
            "include_descendants": spec.include_descendants,
            "valid_from": BASELINE,
            "valid_until": None,
            "revoked_at": None,
            "source_grant_id": None,
            "delegation_depth": 0,
            "version": 1,
        }
        classify(
            existing,
            expected,
            spec,
            "grants",
            findings,
            missing,
            creates,
            unchanged,
        )
    return missing


def inspect_service_grants(
    connection: Connection,
    findings: list[SyntheticFixtureFinding],
    state: list[object],
    creates: dict[str, int],
    unchanged: dict[str, int],
) -> list[SyntheticServiceGrantSpec]:
    units = {item.key: item for item in synthetic_unit_specs()}
    missing: list[SyntheticServiceGrantSpec] = []
    for spec in synthetic_service_grants():
        existing = row(connection, "team_management_grants", "grant_id", spec.grant_id)
        state.append(("service_grant", spec.key, material(existing)))
        expected = {
            "manager_user_id": spec.principal_id,
            "root_unit_id": units[spec.unit_key].unit_id,
            "action": spec.action.value,
            "include_descendants": spec.include_descendants,
            "valid_from": BASELINE,
            "valid_until": None,
            "revoked_at": None,
            "source_grant_id": None,
            "delegation_depth": 0,
            "version": 1,
        }
        classify(
            existing,
            expected,
            spec,
            "grants",
            findings,
            missing,
            creates,
            unchanged,
        )
    return missing
