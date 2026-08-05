"""Regression evidence for one team identity across workflow projections."""

from coeus.repositories.synthetic_organisation_manifest import synthetic_unit_specs
from coeus.repositories.synthetic_workforce import synthetic_team_id


def test_seeded_workflow_teams_use_their_canonical_organisation_unit_identity() -> None:
    units = {unit.key: unit.unit_id for unit in synthetic_unit_specs()}
    expected = {
        "RFA Assessment Team": "rfa_maritime",
        "All-source and Land Assessment": "rfa_land",
        "Cyber and Technical Assessment": "rfa_cyber",
        "Regional and Open-source Assessment": "rfa_regional",
        "Collection Management Team": "cm_open",
        "Geospatial Collection": "cm_geo",
        "Collection Requirements and Coordination": "cm_requirements",
        "JIOC Routing Cell": "jioc",
        "Quality Control Cell": "qc",
    }

    assert {name: synthetic_team_id(name) for name in expected} == {
        name: units[key] for name, key in expected.items()
    }


def test_non_organisational_seed_identifier_keeps_the_legacy_namespace() -> None:
    assert synthetic_team_id("Unmapped test team") == synthetic_team_id("unmapped test TEAM")
