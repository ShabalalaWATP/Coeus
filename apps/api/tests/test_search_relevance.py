from coeus.domain.store_ranking import lexical_text_score, token_overlap


def test_lexical_score_stem_folds_safe_plural_variants() -> None:
    assert (
        lexical_text_score(
            "brief assessment",
            "Briefing note assessments overview",
        )
        > 0
    )
    assert (
        lexical_text_score(
            "sensor radar",
            "Sensors and radars deployment summary",
        )
        > 0
    )
    assert (
        lexical_text_score(
            "vessel",
            "Vessels operating near the strait",
        )
        > 0
    )


def test_lexical_score_does_not_match_cross_word_substrings() -> None:
    assert lexical_text_score("port engin", "Synthetic report engine review") == 0
    assert not token_overlap("port engin", "report engine")
