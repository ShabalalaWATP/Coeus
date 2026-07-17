from coeus.services.search_generation import semantic_generation_usable


def test_ready_and_corpus_stale_generations_remain_queryable() -> None:
    assert semantic_generation_usable("ready", None)
    assert semantic_generation_usable("stale", "corpus_changed")


def test_changed_or_failed_vector_spaces_are_not_queryable() -> None:
    assert not semantic_generation_usable("stale", None)
    assert not semantic_generation_usable("failed", "provider_unavailable")
    assert not semantic_generation_usable("degraded", "index_write_failed")
