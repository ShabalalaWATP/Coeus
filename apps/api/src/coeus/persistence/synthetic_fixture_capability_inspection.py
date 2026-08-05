"""Team and analyst capability inspection for the synthetic fixture."""

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
from coeus.persistence.synthetic_fixture_values import PROVENANCE, delivery_profile_id
from coeus.repositories.synthetic_capability_manifest import (
    SyntheticAnalystCompetencySpec,
    SyntheticTeamCapabilitySpec,
    synthetic_analyst_competencies,
    synthetic_team_capabilities,
)
from coeus.repositories.synthetic_organisation_manifest import BASELINE, synthetic_unit_specs


def inspect_team_capabilities(
    connection: Connection,
    findings: list[SyntheticFixtureFinding],
    state: list[object],
    creates: dict[str, int],
    unchanged: dict[str, int],
) -> list[SyntheticTeamCapabilitySpec]:
    units = {item.key: item for item in synthetic_unit_specs()}
    missing: list[SyntheticTeamCapabilitySpec] = []
    for spec in synthetic_team_capabilities():
        profile_id = delivery_profile_id(units[spec.unit_key].unit_id)
        existing = row(
            connection,
            "team_capability_coverage",
            "coverage_id",
            spec.coverage_id,
        )
        semantic = (
            connection.execute(
                text(
                    "SELECT * FROM team_capability_coverage "
                    "WHERE profile_id=:profile_id AND capability_id=:capability_id "
                    "AND valid_from=:valid_from"
                ),
                {
                    "profile_id": profile_id,
                    "capability_id": spec.capability_id,
                    "valid_from": BASELINE,
                },
            )
            .mappings()
            .first()
        )
        state.append(
            (
                "team_capability",
                spec.unit_key,
                spec.capability_id,
                material(existing),
                material(semantic),
            )
        )
        if existing is None and semantic is not None:
            findings.append(
                finding(
                    "team_capability_collision",
                    "team_capability",
                    f"{spec.unit_key}:{spec.capability_id}",
                    "A local team capability occupies this manifest slot.",
                )
            )
            continue
        expected = {
            "profile_id": profile_id,
            "capability_id": spec.capability_id,
            "proficiency": spec.proficiency,
            "valid_from": BASELINE,
            "valid_until": None,
            "policy_version": 1,
        }
        classify(
            existing,
            expected,
            spec,
            "team_capabilities",
            findings,
            missing,
            creates,
            unchanged,
        )
    return missing


def inspect_competencies(
    connection: Connection,
    users: Mapping[str, SyntheticFixtureUser],
    findings: list[SyntheticFixtureFinding],
    state: list[object],
    creates: dict[str, int],
    unchanged: dict[str, int],
) -> list[SyntheticAnalystCompetencySpec]:
    missing: list[SyntheticAnalystCompetencySpec] = []
    for spec in synthetic_analyst_competencies():
        user = users.get(spec.username.casefold())
        if user is None:
            continue
        existing = row(
            connection,
            "assignment_competencies",
            "competency_id",
            spec.competency_id,
        )
        semantic = (
            connection.execute(
                text(
                    "SELECT * FROM assignment_competencies "
                    "WHERE user_id=:user_id AND capability_id=:capability_id"
                ),
                {"user_id": user.user_id, "capability_id": spec.capability_id},
            )
            .mappings()
            .first()
        )
        state.append(
            (
                "competency",
                spec.username,
                spec.capability_id,
                material(existing),
                material(semantic),
            )
        )
        if existing is None and semantic is not None:
            findings.append(
                finding(
                    "competency_collision",
                    "competency",
                    f"{spec.username}:{spec.capability_id}",
                    "A local competency occupies this manifest slot.",
                )
            )
            continue
        expected = {
            "user_id": user.user_id,
            "capability_id": spec.capability_id,
            "proficiency": spec.proficiency,
            "verified_at": BASELINE,
            "expires_at": None,
            "evidence_reference": "synthetic-exercise-fixture",
            "version": 1,
            "provenance": PROVENANCE,
        }
        classify(
            existing,
            expected,
            spec,
            "competencies",
            findings,
            missing,
            creates,
            unchanged,
        )
    return missing
