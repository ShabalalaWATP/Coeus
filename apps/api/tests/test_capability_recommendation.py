from coeus.persistence.codec import decode_value, encode_value
from coeus.services.capability_catalogue import CapabilityCatalogue
from coeus.services.capability_recommendation import recommend_teams

CATALOGUE = CapabilityCatalogue()


def test_maritime_imagery_request_recommends_the_maritime_imagery_cell() -> None:
    candidates = CATALOGUE.recommend_cm(
        frozenset({"imagery", "vessel", "port"}),
        disciplines=frozenset({"IMINT"}),
        region="Baltic ports",
        priority_tier="P2",
    )

    assert candidates
    assert candidates[0].team_id == "CM-GEO-MARITIME"
    assert len(candidates) <= 3
    assert "capability:keyword:imagery" in candidates[0].reasons
    assert "capability:discipline:imint" in candidates[0].reasons
    assert "capability:region:baltic" in candidates[0].reasons
    assert candidates[0].score > candidates[-1].score or len(candidates) == 1


def test_africa_region_lifts_the_african_imagery_cell() -> None:
    baltic = CATALOGUE.recommend_cm(frozenset({"imagery", "satellite"}), region="Baltic ports")
    africa = CATALOGUE.recommend_cm(
        frozenset({"imagery", "satellite"}), region="Sahel, West Africa"
    )

    assert baltic[0].team_id == "CM-GEO-MARITIME"
    assert africa[0].team_id == "CM-GEO-AFRICA"


def test_teams_without_any_signal_are_never_recommended() -> None:
    candidates = recommend_teams(CATALOGUE.rfa_teams(), terms=frozenset({"zebra", "unrelated"}))

    assert candidates == ()


def test_discipline_preference_can_carry_a_team_without_keyword_overlap() -> None:
    candidates = CATALOGUE.recommend_cm(frozenset({"unrelated"}), disciplines=frozenset({"HUMINT"}))

    assert candidates
    assert candidates[0].team_id == "CM-HUMINT-LIAISON"


def test_recommendations_are_deterministic_with_name_tie_breaks() -> None:
    first = CATALOGUE.recommend_rfa(frozenset({"assessment"}))
    second = CATALOGUE.recommend_rfa(frozenset({"assessment"}))

    assert first == second


def test_high_priority_tiers_prefer_heavyweight_teams() -> None:
    routine = CATALOGUE.recommend_rfa(frozenset({"maritime", "report"}), priority_tier="P4")
    urgent = CATALOGUE.recommend_rfa(frozenset({"maritime", "report"}), priority_tier="P1")

    assert urgent[0].team_id == "RFA-MARITIME"
    assert urgent[0].score >= routine[0].score
    assert "capability:priority-fit:p1" in urgent[0].reasons


def test_best_team_helpers_preserve_triage_fallback_semantics() -> None:
    no_signal = frozenset({"zebra"})

    assert CATALOGUE.best_rfa_team(no_signal).team_id == "RFA-GENERAL"
    assert CATALOGUE.best_cm_team(no_signal) is None
    assert CATALOGUE.default_cm_team().team_id == "CM-GENERAL"


def test_catalogue_teams_carry_disciplines_regions_and_rank() -> None:
    maritime = CATALOGUE.team("RFA-MARITIME")
    africa = CATALOGUE.team("CM-GEO-AFRICA")

    assert maritime is not None and maritime.rank == 0.9
    assert maritime.regions == frozenset({"baltic", "arctic", "north atlantic"})
    assert africa is not None and africa.disciplines == frozenset({"IMINT", "GEOINT"})


def test_candidate_teams_survive_a_codec_round_trip() -> None:
    candidate = CATALOGUE.recommend_rfa(frozenset({"maritime"}))[0]

    assert decode_value(encode_value(candidate)) == candidate
