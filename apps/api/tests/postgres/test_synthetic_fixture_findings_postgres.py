"""Findings the synthetic fixture reports rather than overwriting local data."""

from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from test_synthetic_organisation_fixture_postgres import _upgrade, _users

from coeus.domain.organisation_bootstrap import OrganisationBootstrapPlan
from coeus.persistence.organisation_bootstrap_postgres import PostgresOrganisationBootstrapStore
from coeus.persistence.synthetic_organisation_fixture_postgres import (
    PostgresSyntheticOrganisationFixtureStore,
)
from coeus.repositories.synthetic_organisation_manifest import (
    synthetic_posting_specs,
    synthetic_working_patterns,
)
from coeus.repositories.synthetic_workforce import synthetic_user_id

pytestmark = pytest.mark.postgres
ACTOR = "admin@example.test"


def _codes(preview: object) -> set[str]:
    return {item.code for item in preview.findings}  # type: ignore[attr-defined]


def test_a_clean_database_reports_no_findings(postgres_database_url: str) -> None:
    _upgrade(postgres_database_url)
    engine = create_engine(postgres_database_url)

    preview = PostgresSyntheticOrganisationFixtureStore(engine).preview(
        synthetic_user_id(ACTOR), _users()
    )

    assert preview.can_apply
    assert _codes(preview) == set()
    engine.dispose()


def test_a_missing_seed_identity_is_reported_rather_than_invented(
    postgres_database_url: str,
) -> None:
    _upgrade(postgres_database_url)
    engine = create_engine(postgres_database_url)
    users = _users()[1:]

    preview = PostgresSyntheticOrganisationFixtureStore(engine).preview(
        synthetic_user_id(ACTOR), users
    )

    assert "missing_user" in _codes(preview)
    assert not preview.can_apply
    engine.dispose()


def test_an_active_posting_for_an_inactive_person_is_reported(
    postgres_database_url: str,
) -> None:
    _upgrade(postgres_database_url)
    engine = create_engine(postgres_database_url)
    active_posting = next(
        item for item in synthetic_posting_specs() if item.state.value == "active"
    )
    users = tuple(
        item
        if item.username != active_posting.username
        else type(item)(item.username, item.user_id, False)
        for item in _users()
    )

    preview = PostgresSyntheticOrganisationFixtureStore(engine).preview(
        synthetic_user_id(ACTOR), users
    )

    assert "inactive_user" in _codes(preview)
    engine.dispose()


def test_a_local_posting_that_overlaps_the_fixture_blocks_it(
    postgres_database_url: str,
) -> None:
    _upgrade(postgres_database_url)
    engine = create_engine(postgres_database_url)
    posting = next(item for item in synthetic_posting_specs() if item.valid_until is None)
    unit_id = uuid4()
    PostgresOrganisationBootstrapStore(engine).bootstrap(
        OrganisationBootstrapPlan(
            uuid4(), uuid4(), unit_id, "Local Team", "LOCAL", "Europe/London", ""
        )
    )
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO team_memberships(membership_id,user_id,unit_id,role,state,"
                "assignment_eligible,valid_from,created_by_user_id,reason,provenance,version) "
                "VALUES (:membership,:user,:unit,'member','active',true,:at,:user,"
                "'A local posting.','local',1)"
            ),
            {
                "membership": uuid4(),
                "user": synthetic_user_id(posting.username),
                "unit": unit_id,
                "at": posting.valid_from,
            },
        )

    preview = PostgresSyntheticOrganisationFixtureStore(engine).preview(
        synthetic_user_id(ACTOR), _users()
    )

    assert "posting_overlap" in _codes(preview)
    assert not preview.can_apply
    engine.dispose()


def test_a_non_fixture_row_owning_a_stable_identity_blocks_the_fixture(
    postgres_database_url: str,
) -> None:
    _upgrade(postgres_database_url)
    engine = create_engine(postgres_database_url)
    pattern = synthetic_working_patterns()[0]
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO working_patterns(pattern_id,user_id,time_zone,monday_minutes,"
                "tuesday_minutes,wednesday_minutes,thursday_minutes,friday_minutes,"
                "saturday_minutes,sunday_minutes,valid_from,version,provenance,"
                "created_at,updated_at) VALUES (:pattern,:user,'Europe/London',480,480,480,480,"
                "480,0,0,:at,1,'local',:at,:at)"
            ),
            {
                "pattern": pattern.pattern_id,
                "user": synthetic_user_id(pattern.username),
                "at": pattern.valid_from,
            },
        )

    preview = PostgresSyntheticOrganisationFixtureStore(engine).preview(
        synthetic_user_id(ACTOR), _users()
    )

    assert "fixture_identifier_collision" in _codes(preview)
    assert not preview.can_apply
    engine.dispose()
