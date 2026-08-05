from collections import Counter
from dataclasses import replace

import pytest

import coeus.repositories.synthetic_organisation_integrity as organisation_integrity
from coeus.domain.auth import RoleName
from coeus.domain.organisation import DeliveryRoute, MembershipState
from coeus.repositories.synthetic_calendar_manifest import synthetic_calendar_events
from coeus.repositories.synthetic_capability_manifest import (
    ROUTING_TEAM_UNITS,
    TEAM_CAPABILITIES,
    synthetic_analyst_competencies,
    synthetic_team_capabilities,
)
from coeus.repositories.synthetic_grant_manifest import synthetic_management_grants
from coeus.repositories.synthetic_organisation_integrity import (
    inspect_synthetic_organisation_manifest,
)
from coeus.repositories.synthetic_organisation_manifest import (
    synthetic_posting_specs,
    synthetic_unit_specs,
    synthetic_working_patterns,
)
from coeus.repositories.synthetic_task_manifest import synthetic_task_specs
from coeus.repositories.synthetic_workforce_integrity import inspect_synthetic_workforce
from coeus.repositories.teams import TeamRepository
from coeus.repositories.teams_seed import seed_teams
from coeus.services.capability_catalogue_data import CM_TEAM_SPECS, RFA_TEAM_SPECS
from test_seed_personas import _users


def test_seed_ids_are_stable_and_workforce_integrity_is_machine_readable() -> None:
    first, second = _users(), _users()
    first_ids = {user.username: user.user_id for user in first.list_users()}
    second_ids = {user.username: user.user_id for user in second.list_users()}
    assert first_ids == second_ids
    first_teams, second_teams = TeamRepository(), TeamRepository()
    seed_teams(first_teams, first)
    seed_teams(second_teams, second)
    assert {team.name: team.team_id for team in first_teams.list_teams()} == {
        team.name: team.team_id for team in second_teams.list_teams()
    }
    report = inspect_synthetic_workforce(first.list_users(), first_teams.list_teams())
    assert report.valid
    assert vars(report) == {
        "persona_count": 53,
        "analyst_count": 24,
        "rfa_analyst_count": 14,
        "cm_analyst_count": 10,
        "cross_posted_analyst_count": 0,
        "duplicate_username_count": 0,
        "duplicate_display_name_count": 0,
        "delivery_leaf_shortfalls": (),
        "errors": (),
    }


def test_workforce_integrity_reports_drift_without_repairing_it() -> None:
    users, teams = _users(), TeamRepository()
    seed_teams(teams, users)
    accounts = list(users.list_users())
    accounts[-1] = replace(
        accounts[-1],
        username=accounts[0].username,
        display_name=accounts[0].display_name,
        roles=frozenset({RoleName.USER}),
    )
    seeded_teams = list(teams.list_teams())
    source = next(team for team in seeded_teams if team.name == "RFA Assessment Team")
    target_index = next(
        index
        for index, team in enumerate(seeded_teams)
        if team.name == "Collection Management Team"
    )
    rfa_analyst = next(
        user_id
        for user_id in source.member_user_ids
        if any(
            user.user_id == user_id and RoleName.INTELLIGENCE_ANALYST in user.roles
            for user in accounts
        )
    )
    target = seeded_teams[target_index]
    seeded_teams[target_index] = replace(
        target, member_user_ids=(*target.member_user_ids, rfa_analyst)
    )
    regional_index = next(
        index
        for index, team in enumerate(seeded_teams)
        if team.name == "Regional and Open-source Assessment"
    )
    regional = seeded_teams[regional_index]
    seeded_teams[regional_index] = replace(regional, member_user_ids=())
    report = inspect_synthetic_workforce(tuple(accounts), tuple(seeded_teams))
    assert not report.valid
    assert {
        "analyst_count",
        "rfa_analyst_count",
        "cm_analyst_count",
        "cross_posted_analysts",
        "duplicate_usernames",
        "duplicate_display_names",
        "delivery_leaf_shortfalls",
    } <= set(report.errors)


def test_relational_manifest_is_explicit_acyclic_and_single_home() -> None:
    units = synthetic_unit_specs()
    by_key = {unit.key: unit for unit in units}
    assert len(by_key) == len(units)
    seen: set[str] = set()
    for unit in units:
        assert unit.parent_key is None or unit.parent_key in seen
        seen.add(unit.key)
    assert {
        "Defence Intelligence",
        "DI Joint User",
        "DI NCGIA",
        "MIS",
        "UKSF",
        "SAS",
        "SBS",
        "SRR",
        "18SR",
        "14SR",
        "PAGC",
        "4 RANGERS",
    } <= {unit.name for unit in units}
    delivery = {unit.key: unit.route for unit in units if unit.route is not None}
    assert list(delivery.values()).count(DeliveryRoute.RFA) == 4
    assert list(delivery.values()).count(DeliveryRoute.CM) == 3


def test_relational_postings_encode_exact_analyst_lifecycle_counts() -> None:
    users = {user.username: user for user in _users().list_users()}
    postings = synthetic_posting_specs()
    # One analyst carries a closed prior posting as cross-team transfer evidence,
    # so there is one more posting than there are people.
    assert len(postings) == 54
    assert len({posting.username for posting in postings}) == 53
    assert {posting.username for posting in postings} == set(users)
    open_homes = Counter(
        posting.username for posting in postings if posting.state is not MembershipState.ENDED
    )
    assert set(open_homes.values()) == {1}
    analyst_postings = tuple(
        posting
        for posting in postings
        if RoleName.INTELLIGENCE_ANALYST in users[posting.username].roles
    )
    route_by_unit = {
        unit.key: unit.route for unit in synthetic_unit_specs() if unit.route is not None
    }
    assert sum(route_by_unit[item.unit_key] is DeliveryRoute.RFA for item in analyst_postings) == 15
    assert sum(route_by_unit[item.unit_key] is DeliveryRoute.CM for item in analyst_postings) == 10
    eligible = tuple(item for item in analyst_postings if item.assignment_eligible)
    assert len(eligible) == 21
    assert sum(route_by_unit[item.unit_key] is DeliveryRoute.RFA for item in eligible) == 12
    assert sum(route_by_unit[item.unit_key] is DeliveryRoute.CM for item in eligible) == 9
    assert sum(item.state is MembershipState.ENDED for item in analyst_postings) == 2
    assert sum(item.state is MembershipState.SUSPENDED for item in analyst_postings) == 1
    assert sum(item.valid_from > postings[0].valid_from for item in analyst_postings) == 1
    patterns = synthetic_working_patterns()
    assert len(patterns) == 24
    assert len({pattern.pattern_id for pattern in patterns}) == 24
    part_time = next(item for item in patterns if item.username == "analyst.20@example.test")
    assert part_time.weekday_minutes == 360


def test_relational_manifest_has_controlled_team_and_analyst_capabilities() -> None:
    team_rows = synthetic_team_capabilities()
    analyst_rows = synthetic_analyst_competencies()
    assert len(TEAM_CAPABILITIES) == 7
    assert len(team_rows) == 61
    assert len({item.coverage_id for item in team_rows}) == 61
    assert len(analyst_rows) == 48
    assert len({item.competency_id for item in analyst_rows}) == 48
    assert len({item.username for item in analyst_rows}) == 24
    assert all(
        item.capability_id in TEAM_CAPABILITIES[item.unit_key]
        or ROUTING_TEAM_UNITS.get(item.capability_id) == item.unit_key
        for item in team_rows
    )
    assert len(ROUTING_TEAM_UNITS) == 40
    assert set(ROUTING_TEAM_UNITS) == {str(spec[0]) for spec in (*RFA_TEAM_SPECS, *CM_TEAM_SPECS)}
    report = inspect_synthetic_organisation_manifest()
    assert report.valid
    assert report.unit_count == 25
    assert report.posting_count == 54
    assert report.analyst_count == 24
    assert report.active_eligible_rfa_count == 12
    assert report.active_eligible_cm_count == 9
    assert report.working_pattern_count == 24
    assert report.team_capability_count == 61
    assert report.analyst_competency_count == 48
    assert report.calendar_event_count == 8
    assert report.scoped_management_grant_count == 82
    assert report.task_count == 24
    assert report.active_task_count == 21
    assert report.closed_task_count == 3
    assert report.work_package_count == 48
    assert report.duplicate_stable_id_count == 0
    assert report.delivery_leaf_shortfalls == ()
    events = synthetic_calendar_events()
    assert len(events) == 8
    assert len({item.event_id for item in events}) == 8
    assert sum(item.manager_scope_unit_key is not None for item in events) == 1
    grants = synthetic_management_grants()
    assert len(grants) == 82
    assert len({item.grant_id for item in grants}) == 82
    assert any(
        item.username == "rfa.manager@example.test" and item.include_descendants for item in grants
    )
    tasks = synthetic_task_specs()
    assert len({item.ticket_id for item in tasks}) == 24
    assert len({item.reference for item in tasks}) == 24
    assert {
        item.unit_key for item in tasks if not item.ticket_state.value.startswith("CLOSED_")
    } == {
        "rfa_maritime",
        "rfa_land",
        "rfa_cyber",
        "rfa_regional",
        "cm_open",
        "cm_geo",
        "cm_requirements",
    }
    assert any(
        item.username == "collection.manager@example.test" and item.include_descendants
        for item in grants
    )


def test_relational_integrity_report_exposes_manifest_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    postings = synthetic_posting_specs()
    monkeypatch.setattr(
        organisation_integrity,
        "synthetic_posting_specs",
        lambda: (*postings[:1], postings[0], *postings[2:]),
    )
    monkeypatch.setattr(
        organisation_integrity,
        "synthetic_team_capabilities",
        lambda: (),
    )
    report = organisation_integrity.inspect_synthetic_organisation_manifest()
    assert not report.valid
    assert "single_home_postings" in report.errors
    assert "team_capability_count" in report.errors


def test_routing_mapping_guard_rejects_incomplete_catalogue(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delitem(ROUTING_TEAM_UNITS, "RFA-MARITIME")
    with pytest.raises(RuntimeError, match="mapping is incomplete"):
        synthetic_team_capabilities()
